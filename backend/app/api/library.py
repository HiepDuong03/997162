"""Character + SceneRef library CRUD, and preset listing."""
import os
import shutil
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session, select

from ..db import ASSETS_DIR, get_session
from ..models import Character, SceneRef
from ..prompt_compiler import CAMERA_PRESETS, MOTION_PRESETS

router = APIRouter(prefix="/api", tags=["library"])


# ---- presets (for UI dropdowns) ----
@router.get("/presets")
def presets():
    return {
        "camera": [{"id": k, "label": k.replace("_", " ").title(), "phrase": v} for k, v in CAMERA_PRESETS.items()],
        "motion": [{"id": k, "label": k.replace("_", " ").title(), "phrase": v} for k, v in MOTION_PRESETS.items()],
    }


# ---- characters ----
@router.post("/characters", response_model=Character)
def create_character(c: Character, session: Session = Depends(get_session)):
    c.id = None
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


@router.get("/characters", response_model=list[Character])
def list_characters(session: Session = Depends(get_session)):
    return session.exec(select(Character)).all()


@router.put("/characters/{cid}", response_model=Character)
def update_character(cid: int, patch: Character, session: Session = Depends(get_session)):
    c = session.get(Character, cid)
    if not c:
        raise HTTPException(404, "character not found")
    data = patch.model_dump(exclude_unset=True, exclude={"id", "created_at"})
    for k, v in data.items():
        setattr(c, k, v)
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


@router.post("/characters/{cid}/ref-image", response_model=Character)
def upload_ref_image(cid: int, file: UploadFile = File(...), session: Session = Depends(get_session)):
    c = session.get(Character, cid)
    if not c:
        raise HTTPException(404, "character not found")
    ext = os.path.splitext(file.filename or "")[1] or ".png"
    name = f"char_{cid}_{uuid.uuid4().hex[:8]}{ext}"
    dest = os.path.join(ASSETS_DIR, "refs", name)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    c.ref_image_path = f"refs/{name}"
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


@router.delete("/characters/{cid}")
def delete_character(cid: int, session: Session = Depends(get_session)):
    c = session.get(Character, cid)
    if c:
        session.delete(c)
        session.commit()
    return {"ok": True}


# ---- scene refs ----
@router.post("/scene-refs", response_model=SceneRef)
def create_scene_ref(s: SceneRef, session: Session = Depends(get_session)):
    s.id = None
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


@router.get("/scene-refs", response_model=list[SceneRef])
def list_scene_refs(session: Session = Depends(get_session)):
    return session.exec(select(SceneRef)).all()


@router.put("/scene-refs/{sid}", response_model=SceneRef)
def update_scene_ref(sid: int, patch: SceneRef, session: Session = Depends(get_session)):
    s = session.get(SceneRef, sid)
    if not s:
        raise HTTPException(404, "scene ref not found")
    data = patch.model_dump(exclude_unset=True, exclude={"id", "created_at"})
    for k, v in data.items():
        setattr(s, k, v)
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


@router.delete("/scene-refs/{sid}")
def delete_scene_ref(sid: int, session: Session = Depends(get_session)):
    s = session.get(SceneRef, sid)
    if s:
        session.delete(s)
        session.commit()
    return {"ok": True}
