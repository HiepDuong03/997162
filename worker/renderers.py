"""Renderer implementations behind a single interface.

MockRenderer  — makes a solid-color mp4 with ffmpeg (no GPU). Validates the whole
                pipeline (queue protocol, chained last-frame, upload) on any machine.
ComfyRenderer — drives a headless ComfyUI over its HTTP API using a workflow JSON
                template. Used on the real GPU worker (Phase 2).
"""
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
import uuid
from typing import Optional, Protocol

FFMPEG = os.environ.get("FFMPEG", "ffmpeg")


class RenderResult:
    def __init__(self, clip_path: str, last_frame_path: Optional[str] = None):
        self.clip_path = clip_path
        self.last_frame_path = last_frame_path


class Renderer(Protocol):
    def render(self, task: dict, workdir: str) -> RenderResult: ...


# --------------------------------------------------------------------------- #
# Mock renderer
# --------------------------------------------------------------------------- #
_COLORS = ["red", "green", "blue", "orange", "purple", "teal", "magenta", "navy"]


class MockRenderer:
    """Solid-color clip whose hue is derived from the seed, with the shot's
    prompt burned in as text so you can eyeball which shot is which."""

    def render(self, task: dict, workdir: str) -> RenderResult:
        w, h = task["width"], task["height"]
        frames = task["num_frames"]
        fps = task["fps"]
        dur = max(frames / fps, 1.0)
        color = _COLORS[task["seed"] % len(_COLORS)]
        label = (task.get("prompt") or "shot")[:40].replace(":", " ").replace("'", "")

        clip = os.path.join(workdir, f"clip_{uuid.uuid4().hex[:8]}.mp4")
        # drawtext may be unavailable in some ffmpeg builds; fall back gracefully.
        vf = (
            f"drawtext=text='{label}':fontcolor=white:fontsize=24:"
            f"x=(w-text_w)/2:y=(h-text_h)/2"
        )
        base = [
            FFMPEG, "-y", "-f", "lavfi",
            "-i", f"color=c={color}:s={w}x{h}:d={dur}:r={fps}",
        ]
        try:
            subprocess.run(
                base + ["-vf", vf, "-pix_fmt", "yuv420p", clip],
                check=True, capture_output=True,
            )
        except subprocess.CalledProcessError:
            subprocess.run(base + ["-pix_fmt", "yuv420p", clip], check=True, capture_output=True)

        last_frame = None
        if task.get("needs_last_frame"):
            last_frame = os.path.join(workdir, f"lastframe_{uuid.uuid4().hex[:8]}.png")
            subprocess.run(
                [FFMPEG, "-y", "-sseof", "-0.1", "-i", clip, "-frames:v", "1", last_frame],
                check=True, capture_output=True,
            )
        return RenderResult(clip, last_frame)


# --------------------------------------------------------------------------- #
# ComfyUI renderer (real GPU)
# --------------------------------------------------------------------------- #
class ComfyRenderer:
    def __init__(self, comfy_url: str, workflows_dir: str):
        self.comfy_url = comfy_url.rstrip("/")
        self.workflows_dir = workflows_dir
        self.client_id = uuid.uuid4().hex

    def _load_workflow(self, name: str) -> dict:
        with open(os.path.join(self.workflows_dir, name), "r", encoding="utf-8") as f:
            return json.load(f)

    def _inject(self, wf: dict, task: dict, init_image_name: Optional[str]) -> dict:
        """Fill placeholder tokens in a workflow-API-format JSON.

        Placeholders (string values in node inputs) that get replaced:
        __PROMPT__ __NEGATIVE__ __SEED__ __STEPS__ __HIGH_STEPS__ __CFG__
        __SAMPLER__ __SCHEDULER__ __WIDTH__ __HEIGHT__ __FRAMES__ __FPS__
        __INIT_IMAGE__ __UNET_HIGH__ __UNET_LOW__ __VAE__ __CLIP__
        __LORA_HIGH__ __LORA_LOW__

        A14B is a 2-expert MoE (high-noise expert handles the first
        `high_noise_steps` of the schedule, low-noise expert the rest), so each
        mode needs its own high/low UNet GGUF + its own high/low Lightning LoRA.
        """
        m = task["manifest"]["assets"]
        manifest = task["manifest"]
        if task["mode"] == "i2v":
            unet_high, unet_low = m["unet_high_i2v"], m["unet_low_i2v"]
            lora_high, lora_low = m["lora_i2v_high"], m["lora_i2v_low"]
        else:
            unet_high, unet_low = m["unet_high"], m["unet_low"]
            lora_high, lora_low = m["lora_t2v_high"], m["lora_t2v_low"]
        repl = {
            "__PROMPT__": task["prompt"],
            "__NEGATIVE__": task["negative"],
            "__SEED__": task["seed"],
            "__STEPS__": task["steps"],
            "__HIGH_STEPS__": manifest.get("high_noise_steps", task["steps"] // 2),
            "__CFG__": task["cfg"],
            "__SAMPLER__": task["sampler"],
            "__SCHEDULER__": task["scheduler"],
            "__WIDTH__": task["width"],
            "__HEIGHT__": task["height"],
            "__FRAMES__": task["num_frames"],
            "__FPS__": task["fps"],
            "__INIT_IMAGE__": init_image_name or "",
            "__UNET_HIGH__": unet_high,
            "__UNET_LOW__": unet_low,
            "__VAE__": m["vae"],
            "__CLIP__": m["text_encoder"],
            "__LORA_HIGH__": lora_high,
            "__LORA_LOW__": lora_low,
        }
        raw = json.dumps(wf)
        for k, v in repl.items():
            # numeric placeholders are embedded as strings "__SEED__" in the JSON;
            # replace including surrounding quotes so they become real numbers.
            if isinstance(v, (int, float)):
                raw = raw.replace(f'"{k}"', str(v))
            else:
                raw = raw.replace(k, json.dumps(v)[1:-1])
        return json.loads(raw)

    def _post(self, path: str, payload: dict) -> dict:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{self.comfy_url}{path}", data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())

    def _get(self, path: str) -> dict:
        with urllib.request.urlopen(f"{self.comfy_url}{path}", timeout=30) as r:
            return json.loads(r.read())

    def _upload_image(self, path: str) -> str:
        """Upload an init image to ComfyUI /upload/image; returns stored name."""
        import mimetypes
        boundary = uuid.uuid4().hex
        fname = os.path.basename(path)
        with open(path, "rb") as f:
            content = f.read()
        mime = mimetypes.guess_type(fname)[0] or "image/png"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="image"; filename="{fname}"\r\n'
            f"Content-Type: {mime}\r\n\r\n"
        ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(
            f"{self.comfy_url}/upload/image", data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())["name"]

    def render(self, task: dict, workdir: str) -> RenderResult:
        wf = self._load_workflow(task["workflow"])
        init_name = None
        if task["mode"] == "i2v" and task.get("_init_local_path"):
            init_name = self._upload_image(task["_init_local_path"])
        graph = self._inject(wf, task, init_name)

        resp = self._post("/prompt", {"prompt": graph, "client_id": self.client_id})
        prompt_id = resp["prompt_id"]

        # Poll /history until this prompt_id appears with outputs.
        outputs = None
        for _ in range(600):  # ~10 min ceiling
            hist = self._get(f"/history/{prompt_id}")
            if prompt_id in hist and hist[prompt_id].get("outputs"):
                outputs = hist[prompt_id]["outputs"]
                break
            time.sleep(1)
        if outputs is None:
            raise TimeoutError("ComfyUI render timed out")

        clip_path, frame_path = self._collect_outputs(outputs)
        if clip_path is None:
            raise RuntimeError("no video output found in ComfyUI history")
        return RenderResult(clip_path, frame_path if task.get("needs_last_frame") else None)

    def _collect_outputs(self, outputs: dict) -> tuple[Optional[str], Optional[str]]:
        """Pull the mp4 (gifs/videos) and the last_frame png from ComfyUI /view."""
        clip = frame = None
        for node in outputs.values():
            for key in ("gifs", "videos"):
                for item in node.get(key, []):
                    fn = item["filename"]
                    if fn.lower().endswith((".mp4", ".webm")):
                        clip = self._download_view(item)
            for item in node.get("images", []):
                # last_frame.png is saved with a recognizable prefix in the workflow
                if "last_frame" in item["filename"].lower():
                    frame = self._download_view(item)
        return clip, frame

    def _download_view(self, item: dict) -> str:
        q = urllib.parse.urlencode({
            "filename": item["filename"],
            "subfolder": item.get("subfolder", ""),
            "type": item.get("type", "output"),
        })
        dest = os.path.join(
            os.environ.get("WORKER_TMP", "."), f"dl_{uuid.uuid4().hex[:8]}_{item['filename']}"
        )
        with urllib.request.urlopen(f"{self.comfy_url}/view?{q}", timeout=120) as r:
            with open(dest, "wb") as f:
                f.write(r.read())
        return dest
