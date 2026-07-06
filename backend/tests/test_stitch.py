import os
import shutil
import subprocess

import pytest

from app import services, stitcher
from app.db import ASSETS_DIR
from app.models import ConsistencyMode, Project, Scene, Shot

FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
has_ffmpeg = shutil.which(FFMPEG) is not None


def _fake_clip(rel: str, color: str, dur: float, w: int, h: int):
    dst = os.path.join(ASSETS_DIR, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    subprocess.run(
        [FFMPEG, "-y", "-f", "lavfi", "-i", f"color=c={color}:s={w}x{h}:d={dur}:r=16",
         "-pix_fmt", "yuv420p", dst],
        check=True, capture_output=True,
    )


@pytest.mark.skipif(not has_ffmpeg, reason="ffmpeg not installed")
def test_export_concats_heterogeneous_clips(session):
    p = Project(name="Exp", width=832, height=480, fps=16)
    session.add(p)
    session.commit()
    session.refresh(p)
    # two scenes, 3 shots total, DIFFERENT source resolutions (T4 vs P100 mix)
    sc1 = Scene(project_id=p.id, name="s1", order=0, consistency_mode=ConsistencyMode.parallel)
    sc2 = Scene(project_id=p.id, name="s2", order=1, consistency_mode=ConsistencyMode.parallel)
    session.add(sc1); session.add(sc2); session.commit(); session.refresh(sc1); session.refresh(sc2)

    specs = [
        (sc1.id, 0, "clips/e0.mp4", "red", 832, 480),
        (sc1.id, 1, "clips/e1.mp4", "green", 1280, 720),  # different res
        (sc2.id, 0, "clips/e2.mp4", "blue", 640, 360),     # different res
    ]
    for scid, order, rel, color, w, h in specs:
        _fake_clip(rel, color, 1.0, w, h)
        session.add(Shot(scene_id=scid, order=order, clip_path=rel))
    session.commit()

    rel = stitcher.export_project(session, p)
    out = os.path.join(ASSETS_DIR, rel)
    assert os.path.exists(out) and os.path.getsize(out) > 0

    # duration ~ 3 x 1s = 3s (normalized to 16fps)
    dur = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", out],
        capture_output=True, text=True,
    ).stdout.strip()
    assert 2.5 < float(dur) < 3.7
