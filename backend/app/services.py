"""Business logic: compile a shot's prompt and enqueue a scene's shots as jobs."""
from typing import Optional

from sqlmodel import Session, select

from . import adapters
from .models import (
    Character,
    ConsistencyMode,
    JobStatus,
    Project,
    RenderJob,
    Scene,
    SceneRef,
    Shot,
)
from .prompt_compiler import (
    CharacterInput,
    SceneInput,
    ShotInput,
    compile_prompt,
)


def _parse_char_ids(raw: str) -> list[int]:
    return [int(x) for x in raw.split(",") if x.strip().isdigit()]


def compile_shot(session: Session, shot: Shot, scene: Scene) -> tuple[str, str]:
    chars: list[CharacterInput] = []
    for cid in _parse_char_ids(shot.character_ids):
        c = session.get(Character, cid)
        if c:
            chars.append(
                CharacterInput(
                    name=c.name,
                    appearance=c.appearance,
                    prompt_template=c.prompt_template,
                    negative_prompt=c.negative_prompt,
                )
            )
    scene_in: Optional[SceneInput] = None
    if scene.scene_ref_id:
        sr = session.get(SceneRef, scene.scene_ref_id)
        if sr:
            scene_in = SceneInput(
                environment=sr.environment,
                lighting=sr.lighting,
                style=sr.style,
                time_of_day=sr.time_of_day,
                color_palette=sr.color_palette,
                atmosphere=sr.atmosphere,
                negative_prompt=sr.negative_prompt,
            )
    compiled = compile_prompt(
        ShotInput(
            action_text=shot.action_text,
            camera_preset=shot.camera_preset,
            motion_preset=shot.motion_preset,
            characters=chars,
            scene=scene_in,
        )
    )
    return compiled.prompt, compiled.negative


def _first_char_ref(session: Session, shot: Shot) -> Optional[str]:
    for cid in _parse_char_ids(shot.character_ids):
        c = session.get(Character, cid)
        if c and c.ref_image_path:
            return c.ref_image_path
    return None


def enqueue_scene(session: Session, scene: Scene, priority: int = 0) -> list[RenderJob]:
    """Compile every shot in a scene and create render jobs.

    parallel mode: all shots -> pending, each independent.
    chained mode: shot 0 -> pending (I2V from character ref if available);
                  shots 1..N -> pending_blocked, depends_on previous job.
    """
    shots = session.exec(
        select(Shot).where(Shot.scene_id == scene.id).order_by(Shot.order, Shot.id)
    ).all()
    jobs: list[RenderJob] = []
    prev_job: Optional[RenderJob] = None
    chained = scene.consistency_mode == ConsistencyMode.chained

    for idx, shot in enumerate(shots):
        prompt, negative = compile_shot(session, shot, scene)
        shot.compiled_prompt = prompt
        shot.compiled_negative = negative
        # Anchor first shot (or every parallel shot) to the character ref image.
        if idx == 0 or not chained:
            shot.init_image_path = _first_char_ref(session, shot)
        session.add(shot)
        session.flush()  # ensure shot.id

        if chained and idx > 0:
            status = JobStatus.pending_blocked
        else:
            status = JobStatus.pending

        job = RenderJob(
            shot_id=shot.id,
            status=status,
            priority=priority,
            depends_on_job_id=prev_job.id if (chained and prev_job) else None,
        )
        session.add(job)
        session.flush()
        jobs.append(job)
        prev_job = job

    session.commit()
    for j in jobs:
        session.refresh(j)
    return jobs


def enqueue_project(session: Session, project: Project) -> list[RenderJob]:
    scenes = session.exec(
        select(Scene).where(Scene.project_id == project.id).order_by(Scene.order, Scene.id)
    ).all()
    all_jobs: list[RenderJob] = []
    for scene in scenes:
        all_jobs.extend(enqueue_scene(session, scene))
    return all_jobs


def project_has_rendered_shots(session: Session, project_id: int) -> bool:
    scenes = session.exec(select(Scene).where(Scene.project_id == project_id)).all()
    for sc in scenes:
        shots = session.exec(select(Shot).where(Shot.scene_id == sc.id)).all()
        if any(s.clip_path for s in shots):
            return True
    return False
