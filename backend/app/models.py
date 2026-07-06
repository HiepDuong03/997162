"""SQLModel schema for OpenFlow.

State machine for RenderJob.status:
    pending_blocked -> pending -> claimed -> rendering -> done | failed
`pending_blocked` is used by chained consistency mode: shot N+1 stays blocked
until shot N completes and its last frame is available as I2V input.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ConsistencyMode(str, Enum):
    parallel = "parallel"
    chained = "chained"
    lora = "lora"  # v2 hook, not implemented


class JobStatus(str, Enum):
    pending_blocked = "pending_blocked"
    pending = "pending"
    claimed = "claimed"
    rendering = "rendering"
    done = "done"
    failed = "failed"


class WorkerBootStatus(str, Enum):
    booting = "booting"
    downloading = "downloading"
    ready = "ready"
    rendering = "rendering"
    dead = "dead"


class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: str = ""
    model_id: str = "wan22_a14b"
    # Immutable once any shot is rendered (enforced in API layer).
    width: int = 832
    height: int = 480
    fps: int = 16
    audio_track_url: Optional[str] = None  # v2 hook
    archived_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow)


class Character(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    # Compiled identically into every shot featuring this character.
    appearance: str = ""  # e.g. "young woman, short black hair, red coat, silver pendant"
    prompt_template: str = ""  # extra positive fragments
    negative_prompt: str = ""
    ref_image_path: Optional[str] = None  # canonical reference, used for I2V anchoring
    lora_path: Optional[str] = None  # v2 hook
    seed: int = 42  # base seed; per-scene seed = hash(seed, scene_id)
    created_at: datetime = Field(default_factory=utcnow)


class SceneRef(SQLModel, table=True):
    """Reusable scene/environment preset in the library."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    environment: str = ""
    lighting: str = ""
    camera_setup: str = ""
    style: str = ""
    time_of_day: str = ""
    color_palette: str = ""
    atmosphere: str = ""
    negative_prompt: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class Scene(SQLModel, table=True):
    """An ordered scene inside a project, bound to a SceneRef."""
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    scene_ref_id: Optional[int] = Field(default=None, foreign_key="sceneref.id")
    name: str
    order: int = 0
    consistency_mode: ConsistencyMode = ConsistencyMode.parallel


class Shot(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    scene_id: int = Field(foreign_key="scene.id", index=True)
    order: int = 0
    # comma-separated character ids; SQLite-friendly, parsed in API layer
    character_ids: str = ""
    camera_preset: str = "static"
    motion_preset: str = "none"
    action_text: str = ""
    num_frames: int = 81  # 5s @ 16fps
    seed_override: Optional[int] = None
    # Filled by compiler at enqueue time (snapshot, so library edits don't mutate history)
    compiled_prompt: str = ""
    compiled_negative: str = ""
    # I2V input: ref image (first shot / parallel) or previous shot's last frame (chained)
    init_image_path: Optional[str] = None
    clip_path: Optional[str] = None
    last_frame_path: Optional[str] = None


class RenderJob(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    shot_id: int = Field(foreign_key="shot.id", index=True)
    status: JobStatus = Field(default=JobStatus.pending, index=True)
    priority: int = 0
    retries: int = 0
    max_retries: int = 3
    worker_id: Optional[str] = None
    lease_expires_at: Optional[datetime] = None
    error: Optional[str] = None
    # chained ordering: job that must complete before this one unblocks
    depends_on_job_id: Optional[int] = None
    created_at: datetime = Field(default_factory=utcnow)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class Worker(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    worker_key: str = Field(index=True, unique=True)  # self-chosen uuid from worker
    gpu_name: str = ""
    vram_gb: float = 0
    boot_status: WorkerBootStatus = WorkerBootStatus.booting
    registered_at: datetime = Field(default_factory=utcnow)
