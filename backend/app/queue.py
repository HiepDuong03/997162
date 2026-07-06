"""Queue state machine + in-RAM heartbeat tracking.

Concurrency: claim() runs inside a BEGIN IMMEDIATE transaction so two workers
polling the same SQLite DB can never claim the same job. WAL mode (set in db.py)
keeps UI reads from blocking writers.

Heartbeats are NOT written to the DB — they update an in-process dict. The 60s
sweep reads that dict and does a single DB write per dead worker's jobs.
"""
from datetime import timedelta
from threading import Lock
from typing import Optional

from sqlalchemy import text
from sqlmodel import Session, select

from .models import JobStatus, RenderJob, Shot, utcnow

LEASE_SECONDS = 600          # 10 min
HEARTBEAT_TIMEOUT_SECONDS = 60

# worker_key -> last-seen datetime (naive UTC)
_worker_last_seen: dict[str, "object"] = {}
_hb_lock = Lock()


def touch_worker(worker_key: str) -> None:
    with _hb_lock:
        _worker_last_seen[worker_key] = utcnow()


def worker_alive(worker_key: str) -> bool:
    with _hb_lock:
        ts = _worker_last_seen.get(worker_key)
    if ts is None:
        return False
    return (utcnow() - ts).total_seconds() < HEARTBEAT_TIMEOUT_SECONDS


def claim_job(session: Session, worker_key: str) -> Optional[RenderJob]:
    """Atomically claim the highest-priority pending job. Returns None if none.

    A single `UPDATE ... WHERE id=(SELECT ... LIMIT 1) AND status='pending'
    RETURNING id` is atomic on SQLite (3.35+): two concurrent workers cannot both
    flip the same row because the second one's `AND status='pending'` no longer
    matches. WAL + busy_timeout (db.py) prevents `database is locked` errors.
    """
    now = utcnow()
    lease = now + timedelta(seconds=LEASE_SECONDS)
    sql = text(
        """
        UPDATE renderjob
           SET status='claimed', worker_id=:wk, started_at=:now, lease_expires_at=:lease
         WHERE id = (
             SELECT id FROM renderjob
              WHERE status='pending'
              ORDER BY priority DESC, id ASC
              LIMIT 1
         )
           AND status='pending'
        RETURNING id
        """
    )
    row = session.execute(sql, {"wk": worker_key, "now": now, "lease": lease}).first()
    session.commit()
    if row is None:
        return None
    job = session.get(RenderJob, row[0])
    touch_worker(worker_key)
    return job


def mark_rendering(session: Session, job: RenderJob) -> None:
    job.status = JobStatus.rendering
    job.lease_expires_at = utcnow() + timedelta(seconds=LEASE_SECONDS)
    session.add(job)
    session.commit()


def complete_job(
    session: Session,
    job: RenderJob,
    clip_path: str,
    last_frame_path: Optional[str] = None,
) -> None:
    """Mark done, attach outputs, and unblock the next chained shot if any."""
    job.status = JobStatus.done
    job.finished_at = utcnow()
    job.error = None
    shot = session.get(Shot, job.shot_id)
    if shot:
        shot.clip_path = clip_path
        shot.last_frame_path = last_frame_path
        session.add(shot)
    session.add(job)

    # Unblock dependent chained job(s).
    blocked = session.exec(
        select(RenderJob).where(RenderJob.depends_on_job_id == job.id)
    ).all()
    for b in blocked:
        if b.status == JobStatus.pending_blocked:
            b.status = JobStatus.pending
            # Feed this shot's last frame as the next shot's I2V init image.
            nshot = session.get(Shot, b.shot_id)
            if nshot and last_frame_path:
                nshot.init_image_path = last_frame_path
                session.add(nshot)
            session.add(b)
    session.commit()


def fail_job(session: Session, job: RenderJob, error: str) -> None:
    """Retry with backoff up to max_retries, else terminal fail.
    Terminal failure of a chained job leaves dependents blocked (won't render
    garbage on top of a missing frame)."""
    job.error = error
    if job.retries < job.max_retries:
        job.retries += 1
        job.status = JobStatus.pending
        job.worker_id = None
        job.lease_expires_at = None
        job.started_at = None
    else:
        job.status = JobStatus.failed
        job.finished_at = utcnow()
    session.add(job)
    session.commit()


def sweep_expired(session: Session) -> int:
    """Requeue jobs whose worker missed its heartbeat OR lease expired.
    Returns number of jobs requeued. Called every 60s by the lifespan task."""
    now = utcnow()
    active = session.exec(
        select(RenderJob).where(
            RenderJob.status.in_([JobStatus.claimed, JobStatus.rendering])
        )
    ).all()
    requeued = 0
    for job in active:
        lease_expired = job.lease_expires_at is not None and job.lease_expires_at < now
        hb_dead = job.worker_id is not None and not worker_alive(job.worker_id)
        if lease_expired or hb_dead:
            job.status = JobStatus.pending
            job.worker_id = None
            job.lease_expires_at = None
            job.started_at = None
            session.add(job)
            requeued += 1
    if requeued:
        session.commit()
    return requeued
