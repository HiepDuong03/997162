"""Project / Scene / Shot CRUD + enqueue + progress."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from .. import services, stitcher
from ..db import ASSETS_DIR, get_session
from ..models import (
    JobStatus,
    Project,
    RenderJob,
    Scene,
    Shot,
)

router = APIRouter(prefix="/api", tags=["projects"])


# ---- projects ----
@router.post("/projects", response_model=Project)
def create_project(p: Project, session: Session = Depends(get_session)):
    p.id = None
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


@router.get("/projects", response_model=list[Project])
def list_projects(session: Session = Depends(get_session)):
    return session.exec(select(Project).where(Project.archived_at == None)).all()  # noqa: E711


@router.get("/projects/{pid}", response_model=Project)
def get_project(pid: int, session: Session = Depends(get_session)):
    p = session.get(Project, pid)
    if not p:
        raise HTTPException(404, "project not found")
    return p


@router.put("/projects/{pid}", response_model=Project)
def update_project(pid: int, patch: Project, session: Session = Depends(get_session)):
    p = session.get(Project, pid)
    if not p:
        raise HTTPException(404, "project not found")
    data = patch.model_dump(exclude_unset=True, exclude={"id", "created_at"})
    # resolution immutable once any shot rendered
    if ("width" in data or "height" in data) and services.project_has_rendered_shots(session, pid):
        if data.get("width", p.width) != p.width or data.get("height", p.height) != p.height:
            raise HTTPException(409, "resolution is locked after first render")
    for k, v in data.items():
        setattr(p, k, v)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


@router.post("/projects/{pid}/archive")
def archive_project(pid: int, session: Session = Depends(get_session)):
    from ..models import utcnow
    p = session.get(Project, pid)
    if not p:
        raise HTTPException(404, "project not found")
    p.archived_at = utcnow()
    session.add(p)
    session.commit()
    return {"ok": True}


# ---- scenes ----
@router.post("/scenes", response_model=Scene)
def create_scene(s: Scene, session: Session = Depends(get_session)):
    s.id = None
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


@router.get("/projects/{pid}/scenes", response_model=list[Scene])
def list_scenes(pid: int, session: Session = Depends(get_session)):
    return session.exec(
        select(Scene).where(Scene.project_id == pid).order_by(Scene.order, Scene.id)
    ).all()


@router.put("/scenes/{sid}", response_model=Scene)
def update_scene(sid: int, patch: Scene, session: Session = Depends(get_session)):
    s = session.get(Scene, sid)
    if not s:
        raise HTTPException(404, "scene not found")
    data = patch.model_dump(exclude_unset=True, exclude={"id"})
    for k, v in data.items():
        setattr(s, k, v)
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


# ---- shots ----
@router.post("/shots", response_model=Shot)
def create_shot(shot: Shot, session: Session = Depends(get_session)):
    shot.id = None
    session.add(shot)
    session.commit()
    session.refresh(shot)
    return shot


@router.get("/scenes/{sid}/shots", response_model=list[Shot])
def list_shots(sid: int, session: Session = Depends(get_session)):
    return session.exec(
        select(Shot).where(Shot.scene_id == sid).order_by(Shot.order, Shot.id)
    ).all()


@router.put("/shots/{shid}", response_model=Shot)
def update_shot(shid: int, patch: Shot, session: Session = Depends(get_session)):
    shot = session.get(Shot, shid)
    if not shot:
        raise HTTPException(404, "shot not found")
    data = patch.model_dump(exclude_unset=True, exclude={"id"})
    for k, v in data.items():
        setattr(shot, k, v)
    session.add(shot)
    session.commit()
    session.refresh(shot)
    return shot


@router.delete("/shots/{shid}")
def delete_shot(shid: int, session: Session = Depends(get_session)):
    shot = session.get(Shot, shid)
    if shot:
        session.delete(shot)
        session.commit()
    return {"ok": True}


@router.get("/shots/{shid}/preview-prompt")
def preview_prompt(shid: int, session: Session = Depends(get_session)):
    shot = session.get(Shot, shid)
    if not shot:
        raise HTTPException(404, "shot not found")
    scene = session.get(Scene, shot.scene_id)
    prompt, negative = services.compile_shot(session, shot, scene)
    return {"prompt": prompt, "negative": negative}


# ---- enqueue / render ----
@router.post("/scenes/{sid}/render")
def render_scene(sid: int, session: Session = Depends(get_session)):
    scene = session.get(Scene, sid)
    if not scene:
        raise HTTPException(404, "scene not found")
    jobs = services.enqueue_scene(session, scene)
    return {"enqueued": len(jobs), "job_ids": [j.id for j in jobs]}


@router.post("/projects/{pid}/render")
def render_project(pid: int, session: Session = Depends(get_session)):
    p = session.get(Project, pid)
    if not p:
        raise HTTPException(404, "project not found")
    jobs = services.enqueue_project(session, p)
    return {"enqueued": len(jobs), "job_ids": [j.id for j in jobs]}


@router.post("/projects/{pid}/export")
def export_project(pid: int, session: Session = Depends(get_session)):
    p = session.get(Project, pid)
    if not p:
        raise HTTPException(404, "project not found")
    try:
        rel = stitcher.export_project(session, p)
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"export_path": rel, "url": f"/assets/{rel}"}


@router.get("/projects/{pid}/download")
def download_project(pid: int, path: str, session: Session = Depends(get_session)):
    import os
    abs_path = os.path.join(ASSETS_DIR, path)
    if not os.path.abspath(abs_path).startswith(ASSETS_DIR) or not os.path.exists(abs_path):
        raise HTTPException(404, "export not found")
    return FileResponse(abs_path, media_type="video/mp4", filename=f"project_{pid}.mp4")


@router.get("/projects/{pid}/progress")
def project_progress(pid: int, session: Session = Depends(get_session)):
    scenes = session.exec(select(Scene).where(Scene.project_id == pid)).all()
    scene_ids = [s.id for s in scenes]
    shots = []
    if scene_ids:
        shots = session.exec(select(Shot).where(Shot.scene_id.in_(scene_ids))).all()
    shot_ids = [s.id for s in shots]
    jobs = []
    if shot_ids:
        jobs = session.exec(select(RenderJob).where(RenderJob.shot_id.in_(shot_ids))).all()
    counts: dict[str, int] = {}
    for j in jobs:
        counts[j.status.value] = counts.get(j.status.value, 0) + 1
    total = len(jobs)
    done = counts.get(JobStatus.done.value, 0)
    return {
        "total_jobs": total,
        "done": done,
        "counts": counts,
        "pct": round(100 * done / total, 1) if total else 0.0,
        "shots": [
            {
                "id": s.id,
                "scene_id": s.scene_id,
                "order": s.order,
                "clip_path": s.clip_path,
                "action_text": s.action_text,
            }
            for s in shots
        ],
    }
