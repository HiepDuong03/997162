"""Stitch rendered shot clips into scene/project mp4s.

Clips may come from different workers/resolutions. The concat *demuxer* requires
homogeneous streams, so we normalize every clip (scale + pad + re-encode to a
canonical WxH/fps) into temp files, then concat those. One final H.264 encode.
"""
import os
import subprocess
import tempfile
import uuid

from sqlmodel import Session, select

from .db import ASSETS_DIR
from .models import Project, Scene, Shot

FFMPEG = os.environ.get("FFMPEG", "ffmpeg")


def _abs(rel: str) -> str:
    return os.path.join(ASSETS_DIR, rel)


def _normalize(src: str, w: int, h: int, fps: int, dst: str) -> None:
    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}"
    )
    subprocess.run(
        [FFMPEG, "-y", "-i", src, "-vf", vf, "-c:v", "libx264", "-crf", "18",
         "-pix_fmt", "yuv420p", "-an", dst],
        check=True, capture_output=True,
    )


def _concat(parts: list[str], dst: str) -> None:
    listfile = dst + ".txt"
    with open(listfile, "w", encoding="utf-8") as f:
        for p in parts:
            f.write(f"file '{p.replace(chr(92), '/')}'\n")
    subprocess.run(
        [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", listfile,
         "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", dst],
        check=True, capture_output=True,
    )
    os.remove(listfile)


def _ordered_clips(session: Session, project: Project) -> list[str]:
    scenes = session.exec(
        select(Scene).where(Scene.project_id == project.id).order_by(Scene.order, Scene.id)
    ).all()
    clips: list[str] = []
    for sc in scenes:
        shots = session.exec(
            select(Shot).where(Shot.scene_id == sc.id).order_by(Shot.order, Shot.id)
        ).all()
        for sh in shots:
            if sh.clip_path:
                clips.append(_abs(sh.clip_path))
    return clips


def export_project(session: Session, project: Project) -> str:
    """Returns the assets-relative path of the exported mp4. Raises if no clips."""
    clips = _ordered_clips(session, project)
    if not clips:
        raise ValueError("no rendered shots to export")

    tmp = tempfile.mkdtemp(prefix="of_export_")
    norm_parts: list[str] = []
    try:
        for i, c in enumerate(clips):
            dst = os.path.join(tmp, f"n_{i:04d}.mp4")
            _normalize(c, project.width, project.height, project.fps, dst)
            norm_parts.append(dst)
        out_name = f"project_{project.id}_{uuid.uuid4().hex[:8]}.mp4"
        out_abs = _abs(os.path.join("exports", out_name))
        _concat(norm_parts, out_abs)
        return f"exports/{out_name}"
    finally:
        for p in norm_parts:
            try:
                os.remove(p)
            except OSError:
                pass
        try:
            os.rmdir(tmp)
        except OSError:
            pass
