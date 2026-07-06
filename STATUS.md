# OpenFlow — STATUS

_Checkpoint file. Any agent: read this + CLAUDE.md before doing anything._

## Where things stand (2026-07-06)

MVP core pipeline is **built and verified end-to-end on this machine** (no GPU) via the mock worker.

| Phase | State | Gate result |
|-------|-------|-------------|
| 1 — Backend core + queue | ✅ done | 12 pytest pass incl. concurrency no-double-claim, chained unblock, lease-expiry requeue, retry-exhaustion |
| 1.5 — Local dry-run worker | ✅ done | mock worker renders + uploads clips; chained t2v→i2v→i2v propagation verified; workflow JSON templating validated |
| 2 — Kaggle GPU worker | ⏳ artifacts done, **needs user smoke test** | notebook + bootstrap + workflow JSONs written & templating-validated; running on real Kaggle GPU is a user step |
| 3 — Frontend | ✅ done | full click-through verified in browser preview; live WS progress; worker chips; export |
| 4 — Stitch + export + resilience | ✅ done | export test: 3 heterogeneous-res clips → one 15.19s 832×480 mp4 |

## Verified working
- Projects → Scenes → Shots hierarchy, character + scene libraries.
- Prompt compiler: truncation-safe order `[action]→[identity]→[scene]→[camera]→[quality]`, merged/deduped negatives.
- Queue: atomic `UPDATE...RETURNING` claim (race-safe on SQLite WAL), in-RAM heartbeat, 60s sweep, chained `pending_blocked` unblock-on-complete feeding last-frame as next I2V input.
- Mock worker (`worker.py --mock`) — full pipeline on any machine, no GPU.
- Export: normalize-then-concat handles mixed worker resolutions.

## Next steps
1. **User: run the real Kaggle smoke test** — build the private Dataset with the 4 model files (see README), run `kaggle_worker.ipynb`, confirm one Wan 2.2 shot renders into the UI.
2. Then: v1.5 RunPod adapter, upscale/interp pass, audio pipeline (schema column already present).

## Known-noise / gotchas
- `MockRenderer` warns "low system RAM" on this box (~1GB free) — cosmetic, mock still renders.
- Frontend is **Vite + React SPA**, not Next.js (approved deviation — backend fully decoupled, no SSR need). Proxy points at backend :8020 here because :8000 was taken by another local server.
- ComfyUI workflow uses `UnetLoaderGGUF` (city96) + `ImageSelect` for last-frame. If a node name differs in your ComfyUI build, adjust the workflow JSON — templating only fills `__TOKENS__`.

## Run locally
```
# backend
cd backend && .venv/Scripts/python -m uvicorn app.main:app --port 8020
# frontend
cd frontend && npm run dev            # http://localhost:5273
# mock worker (no GPU)
cd worker && BACKEND=http://127.0.0.1:8020 python worker.py --mock
# tests
cd backend && .venv/Scripts/python -m pytest -q
```
