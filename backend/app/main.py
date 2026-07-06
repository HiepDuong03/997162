import asyncio
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from . import queue
from .db import ASSETS_DIR, engine, init_db
from .api import library, projects, workers

SWEEP_INTERVAL_SECONDS = 60


async def _sweep_loop():
    while True:
        await asyncio.sleep(SWEEP_INTERVAL_SECONDS)
        try:
            with Session(engine) as s:
                n = queue.sweep_expired(s)
                if n:
                    print(f"[sweep] requeued {n} stale job(s)")
        except Exception as e:  # keep the loop alive
            print(f"[sweep] error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    task = asyncio.create_task(_sweep_loop())
    yield
    task.cancel()


app = FastAPI(title="OpenFlow", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(library.router)
app.include_router(projects.router)
app.include_router(workers.router)

os.makedirs(ASSETS_DIR, exist_ok=True)
app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


@app.get("/api/health")
def health():
    return {"ok": True, "service": "openflow"}


@app.get("/api/models")
def models():
    from . import adapters
    return list(adapters.load_all().values())


@app.websocket("/ws/projects/{pid}")
async def project_ws(websocket: WebSocket, pid: int):
    """Push project progress every 2s. Simple poll-and-push; MVP-scoped."""
    await websocket.accept()
    from .api.projects import project_progress
    try:
        while True:
            with Session(engine) as s:
                data = project_progress(pid, s)
            await websocket.send_text(json.dumps(data, default=str))
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return
    except Exception:
        await websocket.close()
