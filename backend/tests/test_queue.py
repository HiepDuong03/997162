import threading
import time
from datetime import timedelta

from app import queue, services
from app.models import (
    Character,
    ConsistencyMode,
    JobStatus,
    Project,
    RenderJob,
    Scene,
    Shot,
    utcnow,
)
from app.db import engine
from sqlmodel import Session, select


def _make_scene(session, mode=ConsistencyMode.parallel, n_shots=3):
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)
    sc = Scene(project_id=p.id, name="S", consistency_mode=mode)
    session.add(sc)
    session.commit()
    session.refresh(sc)
    for i in range(n_shots):
        session.add(Shot(scene_id=sc.id, order=i, action_text=f"shot {i}"))
    session.commit()
    return p, sc


def test_enqueue_parallel_all_pending(session):
    _, sc = _make_scene(session, ConsistencyMode.parallel, 3)
    jobs = services.enqueue_scene(session, sc)
    assert len(jobs) == 3
    assert all(j.status == JobStatus.pending for j in jobs)


def test_enqueue_chained_blocks_all_but_first(session):
    _, sc = _make_scene(session, ConsistencyMode.chained, 3)
    jobs = services.enqueue_scene(session, sc)
    assert jobs[0].status == JobStatus.pending
    assert jobs[1].status == JobStatus.pending_blocked
    assert jobs[2].status == JobStatus.pending_blocked
    assert jobs[1].depends_on_job_id == jobs[0].id
    assert jobs[2].depends_on_job_id == jobs[1].id


def test_chained_unblock_on_complete(session):
    _, sc = _make_scene(session, ConsistencyMode.chained, 3)
    jobs = services.enqueue_scene(session, sc)
    j0 = queue.claim_job(session, "w1")
    assert j0.id == jobs[0].id
    # nothing else claimable yet
    assert queue.claim_job(session, "w2") is None
    queue.complete_job(session, j0, "clips/a.mp4", "frames/a.png")
    # now shot 1 is unblocked, and its init image is the previous last frame
    j1 = queue.claim_job(session, "w2")
    assert j1.id == jobs[1].id
    sh1 = session.get(Shot, j1.shot_id)
    assert sh1.init_image_path == "frames/a.png"


def test_no_double_claim_concurrent(session):
    """The core race test: many threads claim; each job claimed at most once."""
    _, sc = _make_scene(session, ConsistencyMode.parallel, 20)
    services.enqueue_scene(session, sc)

    claimed_ids: list[int] = []
    lock = threading.Lock()

    def worker(name):
        # each thread uses its own Session on the shared engine
        with Session(engine) as s:
            while True:
                j = queue.claim_job(s, name)
                if j is None:
                    break
                with lock:
                    claimed_ids.append(j.id)
                time.sleep(0.001)

    threads = [threading.Thread(target=worker, args=(f"w{i}",)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(claimed_ids) == 20
    assert len(set(claimed_ids)) == 20  # no duplicates


def test_lease_expiry_requeues(session):
    _, sc = _make_scene(session, ConsistencyMode.parallel, 1)
    services.enqueue_scene(session, sc)
    j = queue.claim_job(session, "w1")
    # force lease into the past and mark worker dead (no heartbeat)
    j.lease_expires_at = utcnow() - timedelta(seconds=1)
    session.add(j)
    session.commit()
    queue._worker_last_seen.pop("w1", None)
    n = queue.sweep_expired(session)
    assert n == 1
    session.refresh(j)
    assert j.status == JobStatus.pending


def test_fail_retries_then_terminal(session):
    _, sc = _make_scene(session, ConsistencyMode.parallel, 1)
    services.enqueue_scene(session, sc)
    j = queue.claim_job(session, "w1")
    for _ in range(3):
        queue.fail_job(session, j, "boom")
        assert j.status == JobStatus.pending  # retried
        j = queue.claim_job(session, "w1")
    queue.fail_job(session, j, "boom")
    assert j.status == JobStatus.failed  # exhausted 3 retries
