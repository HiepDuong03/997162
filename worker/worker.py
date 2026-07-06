"""OpenFlow GPU/mock worker.

Polls the backend over HTTP (works from Kaggle/Colab behind Cloudflare Tunnel —
no inbound ports). One process = one renderer.

    python worker.py --mock                      # no GPU, ffmpeg solid-color clips
    python worker.py --comfy --comfy-url http://127.0.0.1:8188
    BACKEND=https://xxx.trycloudflare.com python worker.py --comfy

Resilience:
  * heartbeat every 30s in a background thread (in-RAM on the backend)
  * downloads (init images) retry 3x with timeout before invoking the renderer
  * clip written to disk first, then /complete uploaded with 10/30/90s backoff
"""
import argparse
import os
import shutil
import tempfile
import time
import traceback
import uuid
from threading import Event, Thread

import requests

BACKEND = os.environ.get("BACKEND", "http://127.0.0.1:8000").rstrip("/")
HEARTBEAT_SECONDS = 30
POLL_IDLE_SECONDS = 3
UPLOAD_BACKOFF = [10, 30, 90]


def gpu_info():
    try:
        import torch  # noqa
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            return name, round(vram, 1)
    except Exception:
        pass
    return "cpu/mock", 0.0


def check_system_ram(threshold_gb: float = 2.0):
    """Warn if system RAM headroom is low (Kaggle OOM-kill risk)."""
    try:
        import psutil
        avail = psutil.virtual_memory().available / (1024**3)
        if avail < threshold_gb:
            print(f"[warn] low system RAM: {avail:.1f}GB available")
        return avail
    except Exception:
        return None


class Worker:
    def __init__(self, renderer, worker_key: str, boot_status: str = "ready"):
        self.renderer = renderer
        self.key = worker_key
        self.session = requests.Session()
        self.stop = Event()
        gpu_name, vram = gpu_info()
        self.gpu_name, self.vram = gpu_name, vram
        self.boot_status = boot_status

    # ---- backend calls ----
    def register(self):
        self.session.post(
            f"{BACKEND}/api/worker/register",
            json={
                "worker_key": self.key, "gpu_name": self.gpu_name,
                "vram_gb": self.vram, "boot_status": self.boot_status,
            },
            timeout=30,
        )
        print(f"[worker {self.key}] registered gpu={self.gpu_name} vram={self.vram}GB")

    def heartbeat_loop(self):
        while not self.stop.wait(HEARTBEAT_SECONDS):
            try:
                self.session.post(
                    f"{BACKEND}/api/worker/heartbeat",
                    json={"worker_key": self.key}, timeout=15,
                )
            except Exception as e:
                print(f"[hb] {e}")

    def claim(self):
        r = self.session.post(
            f"{BACKEND}/api/worker/claim", params={"worker_key": self.key}, timeout=30
        )
        r.raise_for_status()
        return r.json()["job"]

    def download_init_image(self, task, workdir):
        url = task.get("init_image_url")
        if not url:
            return None
        full = url if url.startswith("http") else f"{BACKEND}{url}"
        dest = os.path.join(workdir, f"init_{uuid.uuid4().hex[:8]}.png")
        for attempt in range(3):
            try:
                resp = self.session.get(full, timeout=30)
                resp.raise_for_status()
                with open(dest, "wb") as f:
                    f.write(resp.content)
                return dest
            except Exception as e:
                if attempt == 2:
                    raise
                print(f"[dl] retry init image ({e})")
                time.sleep(5)

    def upload_complete(self, job_id, clip_path, last_frame_path):
        for i, backoff in enumerate([0] + UPLOAD_BACKOFF):
            if backoff:
                time.sleep(backoff)
            try:
                files = {"clip": ("clip.mp4", open(clip_path, "rb"), "video/mp4")}
                if last_frame_path and os.path.exists(last_frame_path):
                    files["last_frame"] = ("last_frame.png", open(last_frame_path, "rb"), "image/png")
                r = self.session.post(
                    f"{BACKEND}/api/worker/complete",
                    data={"worker_key": self.key, "job_id": str(job_id)},
                    files=files, timeout=180,
                )
                r.raise_for_status()
                return True
            except Exception as e:
                print(f"[upload] attempt {i} failed: {e}")
        return False

    def report_fail(self, job_id, error):
        try:
            self.session.post(
                f"{BACKEND}/api/worker/fail",
                json={"worker_key": self.key, "job_id": job_id, "error": error[:500]},
                timeout=30,
            )
        except Exception as e:
            print(f"[fail-report] {e}")

    def mark_rendering(self, job_id):
        try:
            self.session.post(
                f"{BACKEND}/api/worker/rendering",
                json={"worker_key": self.key, "job_id": job_id}, timeout=15,
            )
        except Exception:
            pass

    # ---- main loop ----
    def run_once(self):
        task = self.claim()
        if not task:
            return False
        job_id = task["job_id"]
        print(f"[worker {self.key}] claimed job {job_id} shot {task['shot_id']} ({task['mode']})")
        workdir = tempfile.mkdtemp(prefix="of_job_")
        try:
            check_system_ram()
            init_local = self.download_init_image(task, workdir)
            if init_local:
                task["_init_local_path"] = init_local
            self.mark_rendering(job_id)
            result = self.renderer.render(task, workdir)
            ok = self.upload_complete(job_id, result.clip_path, result.last_frame_path)
            if ok:
                print(f"[worker {self.key}] completed job {job_id}")
            else:
                self.report_fail(job_id, "upload failed after retries")
        except Exception:
            err = traceback.format_exc()
            print(f"[worker {self.key}] job {job_id} error:\n{err}")
            self.report_fail(job_id, err)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        return True

    def serve(self):
        self.register()
        Thread(target=self.heartbeat_loop, daemon=True).start()
        print(f"[worker {self.key}] polling {BACKEND} ...")
        while not self.stop.is_set():
            try:
                did_work = self.run_once()
            except Exception as e:
                print(f"[loop] {e}")
                did_work = False
            if not did_work:
                time.sleep(POLL_IDLE_SECONDS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="ffmpeg solid-color renderer (no GPU)")
    ap.add_argument("--comfy", action="store_true", help="drive headless ComfyUI")
    ap.add_argument("--comfy-url", default=os.environ.get("COMFY_URL", "http://127.0.0.1:8188"))
    ap.add_argument("--workflows", default=os.path.join(os.path.dirname(__file__), "comfy_workflows"))
    ap.add_argument("--key", default=os.environ.get("WORKER_KEY", f"worker-{uuid.uuid4().hex[:6]}"))
    ap.add_argument("--once", action="store_true", help="process a single job then exit (testing)")
    args = ap.parse_args()

    if args.comfy:
        from renderers import ComfyRenderer
        renderer = ComfyRenderer(args.comfy_url, args.workflows)
    else:
        from renderers import MockRenderer
        renderer = MockRenderer()

    w = Worker(renderer, args.key)
    if args.once:
        w.register()
        while not w.run_once():
            time.sleep(POLL_IDLE_SECONDS)
    else:
        try:
            w.serve()
        except KeyboardInterrupt:
            w.stop.set()


if __name__ == "__main__":
    main()
