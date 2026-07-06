# OpenFlow

An AI video-generation tool built as an **orchestration layer** over open-source
video models (Wan 2.2 first), not a thin model wrapper. It competes with
Higgsfield / Google Flow on *workflow*: Project → Scene → Shot, character &
scene reference libraries, auto-compiled cinematic prompts, and parallel
rendering on **free GPUs** (Kaggle/Colab) — stitched and exported up to 10 min.

The speed lever that makes this practical: **Wan2.2-Lightning distill LoRAs run
at 4 steps with CFG=1 (~20× faster)**, so a 5-second 480p shot renders in
~90–150s on a free T4 instead of 15–25 min at 40 steps. Long videos are just
many short shots rendered in parallel across workers.

## Architecture

```
Browser (Vite/React SPA, Flow-like UI)
   │  REST + WebSocket
FastAPI backend (local)  ── SQLite (WAL)  ── assets/ (refs, clips, exports)
   │
HTTP-pull job queue      ← workers POLL over the internet (no inbound ports)
   ▲  /claim /heartbeat /complete /fail
Kaggle / Colab worker notebook
   └─ headless ComfyUI + Wan2.2 A14B GGUF + Lightning LoRA
```

Workers pull work over HTTP, so they run fine on Kaggle/Colab which forbid
inbound ports. Expose the local backend to workers with a **Cloudflare Tunnel**.

## Repo layout
- `backend/` — FastAPI + SQLModel. Queue, prompt compiler, model adapters, stitcher.
- `worker/`  — `worker.py` (poll loop, `--mock` and `--comfy`), ComfyUI workflow JSONs, Kaggle notebook.
- `frontend/`— React SPA (projects, shot composer, library, live progress).
- `backend/adapters/*.json` — capability manifests. Add a model = drop in a manifest + workflow JSON, **no UI change**.

## Quick start (local, no GPU)

```bash
# 1. backend
cd backend
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m uvicorn app.main:app --port 8020

# 2. frontend
cd ../frontend && npm install && npm run dev      # http://localhost:5273

# 3. mock worker — renders solid-color test clips, exercises the whole pipeline
cd ../worker && BACKEND=http://127.0.0.1:8020 python worker.py --mock
```

Open the app, add a character (Library), create a project → scene → shots,
click **Render all**, watch clips fill in live, then **Export mp4**.

Run tests: `cd backend && .venv/Scripts/python -m pytest -q`

## Real rendering on Kaggle (free GPU)

1. **Build a private Kaggle Dataset** with the 4 model files:
   - Wan 2.2 A14B UNet **GGUF** (Q4_K_M or Q5_K_M) — from `city96` / `QuantStack` GGUF repos.
   - **UMT5-xxl text encoder, fp8** (`umt5-xxl-encoder-fp8_e4m3fn`). The full fp16 (~10GB) will not fit alongside the model on a T4.
   - **Wan 2.2 VAE**.
   - **Lightning LoRAs** (both `t2v-a14b-4steps` and `i2v-a14b-4steps`) from `lightx2v/Wan2.2-Lightning`.
   File names must match `backend/adapters/wan22_a14b.json` (or edit that manifest).
2. Start the backend + a **Cloudflare Tunnel**:
   ```bash
   cloudflared tunnel --url http://127.0.0.1:8020
   ```
   Copy the `https://xxxx.trycloudflare.com` URL.
3. Open `worker/kaggle_worker.ipynb` on Kaggle. Accelerator = **GPU T4 ×2**, Internet **On**, attach your Dataset. Set `BACKEND` to the tunnel URL. Run all cells.
4. In the app, click **Render all** — shots render on Kaggle and stream back into the UI.

### Cold start & free-tier math
First run per Kaggle session is **5–15 min** (ComfyUI install + model load); the
UI shows a per-worker status chip (`booting → downloading → ready → rendering`).
Cache the models as a Dataset so they aren't re-downloaded.

Kaggle gives ~**30 GPU-hours/week**. At ~2 min/shot (render + overhead) that is
~**700–900 shots/week** ≈ 6–7 ten-minute videos per account, single worker.
Kaggle's 2×T4 lets you run a second ComfyUI + worker for roughly double. This is
the free tier's real ceiling — for more, add a RunPod/Modal worker (same
`worker.py`, just point `BACKEND` at the tunnel and give it a bigger GPU).

## Character consistency
Per-scene `consistency_mode`:
- **parallel** (default): every shot compiled with the same locked character
  prompt + fixed seed, first shot anchored to the character's reference image via
  I2V. Fast; style-level consistency.
- **chained**: each shot uses the **previous shot's last frame** as its I2V input
  — strong identity across a scene, at the cost of rendering that scene's shots
  in order (different scenes still run in parallel).
- **lora**: schema hook for trained per-character LoRAs (v2).

## Not in the MVP (schema hooks exist)
Timeline editor, audio/TTS (`audio_track_url` column present), character-LoRA
training, RIFE interpolation/upscale, RunPod/Modal autoscaling, multi-user auth.
