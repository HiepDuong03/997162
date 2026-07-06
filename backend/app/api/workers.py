"""Worker-facing endpoints: register, claim, heartbeat, complete, fail.

Workers POLL these over the internet (Cloudflare Tunnel). No inbound ports on
the worker side — required for Kaggle/Colab.
"""
import os
import shutil
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import adapters, queue
from ..db import ASSETS_DIR, engine, get_session
from ..models import (
    Project,
    RenderJob,
    Scene,
    Shot,
    Worker,
    WorkerBootStatus,
)

router = APIRouter(prefix="/api/worker", tags=["worker"])


class RegisterIn(BaseModel):
    worker_key: str
    gpu_name: str = ""
    vram_gb: float = 0
    boot_status: WorkerBootStatus = WorkerBootStatus.ready


@router.post("/register", response_model=Worker)
def register(body: RegisterIn, session: Session = Depends(get_session)):
    w = session.exec(select(Worker).where(Worker.worker_key == body.worker_key)).first()
    if w is None:
        w = Worker(worker_key=body.worker_key)
    w.gpu_name = body.gpu_name
    w.vram_gb = body.vram_gb
    w.boot_status = body.boot_status
    session.add(w)
    session.commit()
    session.refresh(w)
    queue.touch_worker(body.worker_key)
    return w


class BootStatusIn(BaseModel):
    worker_key: str
    boot_status: WorkerBootStatus


@router.post("/boot-status")
def boot_status(body: BootStatusIn, session: Session = Depends(get_session)):
    w = session.exec(select(Worker).where(Worker.worker_key == body.worker_key)).first()
    if not w:
        raise HTTPException(404, "unknown worker")
    w.boot_status = body.boot_status
    session.add(w)
    session.commit()
    return {"ok": True}


class HeartbeatIn(BaseModel):
    worker_key: str


@router.post("/heartbeat")
def heartbeat(body: HeartbeatIn):
    # NO DB write — in-RAM only. Sweep task consults this.
    queue.touch_worker(body.worker_key)
    return {"ok": True}


def _build_task(session: Session, job: RenderJob) -> dict:
    """Assemble the full render instruction for the worker."""
    shot = session.get(Shot, job.shot_id)
    scene = session.get(Scene, shot.scene_id)
    project = session.get(Project, scene.project_id)
    worker = session.exec(select(Worker).where(Worker.worker_key == job.worker_id)).first()
    vram = worker.vram_gb if worker else 0
    manifest = adapters.get(project.model_id)

    # Resolution: project res if the GPU can do it, else best it can.
    res_name, w_res, h_res = adapters.resolve_resolution(project.model_id, vram)
    width, height = project.width, project.height
    # Never exceed what the GPU supports.
    if w_res * h_res < width * height:
        width, height = w_res, h_res

    is_i2v = bool(shot.init_image_path) and manifest.get("supports_i2v")
    workflow = manifest["workflow_i2v"] if is_i2v else manifest["workflow_t2v"]
    seed = shot.seed_override if shot.seed_override is not None else (job.shot_id * 1000 + 7)

    return {
        "job_id": job.id,
        "shot_id": shot.id,
        "model_id": project.model_id,
        "manifest": manifest,
        "workflow": workflow,
        "mode": "i2v" if is_i2v else "t2v",
        "prompt": shot.compiled_prompt,
        "negative": shot.compiled_negative,
        "width": width,
        "height": height,
        "num_frames": shot.num_frames,
        "fps": project.fps,
        "seed": seed,
        "steps": manifest["steps"],
        "cfg": manifest["cfg"],
        "sampler": manifest["sampler"],
        "scheduler": manifest["scheduler"],
        "init_image_url": f"/assets/{shot.init_image_path}" if shot.init_image_path else None,
        "needs_last_frame": scene.consistency_mode.value == "chained",
    }


@router.post("/claim")
def claim(worker_key: str, session: Session = Depends(get_session)):
    job = queue.claim_job(session, worker_key)
    if job is None:
        return {"job": None}
    task = _build_task(session, job)
    return {"job": task}


class ProgressIn(BaseModel):
    worker_key: str
    job_id: int


@router.post("/rendering")
def rendering(body: ProgressIn, session: Session = Depends(get_session)):
    job = session.get(RenderJob, body.job_id)
    if job:
        queue.mark_rendering(session, job)
        queue.touch_worker(body.worker_key)
    return {"ok": True}


@router.post("/complete")
def complete(
    worker_key: str = Form(...),
    job_id: int = Form(...),
    clip: UploadFile = File(...),
    last_frame: Optional[UploadFile] = File(None),
    session: Session = Depends(get_session),
):
    job = session.get(RenderJob, job_id)
    if not job:
        raise HTTPException(404, "job not found")

    clip_name = f"clip_{job.shot_id}_{uuid.uuid4().hex[:8]}.mp4"
    clip_dest = os.path.join(ASSETS_DIR, "clips", clip_name)
    with open(clip_dest, "wb") as f:
        shutil.copyfileobj(clip.file, f)
    clip_rel = f"clips/{clip_name}"

    frame_rel = None
    if last_frame is not None:
        fr_name = f"frame_{job.shot_id}_{uuid.uuid4().hex[:8]}.png"
        fr_dest = os.path.join(ASSETS_DIR, "frames", fr_name)
        with open(fr_dest, "wb") as f:
            shutil.copyfileobj(last_frame.file, f)
        frame_rel = f"frames/{fr_name}"

    queue.complete_job(session, job, clip_rel, frame_rel)
    queue.touch_worker(worker_key)
    return {"ok": True}


class FailIn(BaseModel):
    worker_key: str
    job_id: int
    error: str = ""


@router.post("/fail")
def fail(body: FailIn, session: Session = Depends(get_session)):
    job = session.get(RenderJob, body.job_id)
    if not job:
        raise HTTPException(404, "job not found")
    queue.fail_job(session, job, body.error)
    queue.touch_worker(body.worker_key)
    return {"ok": True, "status": job.status.value, "retries": job.retries}


@router.get("/list", response_model=list[Worker])
def list_workers(session: Session = Depends(get_session)):
    return session.exec(select(Worker)).all()
