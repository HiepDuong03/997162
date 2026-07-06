import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    # Entering the context manager triggers the lifespan (init_db).
    with TestClient(app) as c:
        yield c


def test_end_to_end_flow(client):
    # health
    assert client.get("/api/health").json()["ok"] is True

    # character + scene ref
    ch = client.post("/api/characters", json={"name": "Elara", "appearance": "red coat"}).json()
    sr = client.post("/api/scene-refs", json={"name": "Forest", "environment": "foggy forest"}).json()

    # project -> scene -> shot
    proj = client.post("/api/projects", json={"name": "Demo"}).json()
    scene = client.post(
        "/api/scenes",
        json={"project_id": proj["id"], "name": "S1", "scene_ref_id": sr["id"]},
    ).json()
    shot = client.post(
        "/api/shots",
        json={
            "scene_id": scene["id"],
            "action_text": "walks into the clearing",
            "camera_preset": "slow_push_in",
            "motion_preset": "walking",
            "character_ids": str(ch["id"]),
        },
    ).json()

    # preview prompt reflects compiler
    pv = client.get(f"/api/shots/{shot['id']}/preview-prompt").json()
    assert "walks into the clearing" in pv["prompt"]
    assert "foggy forest" in pv["prompt"]

    # render scene -> job enqueued
    r = client.post(f"/api/scenes/{scene['id']}/render").json()
    assert r["enqueued"] == 1

    # worker registers, claims, completes
    client.post(
        "/api/worker/register",
        json={"worker_key": "wk1", "gpu_name": "T4", "vram_gb": 16},
    )
    claim = client.post("/api/worker/claim", params={"worker_key": "wk1"}).json()
    assert claim["job"] is not None
    task = claim["job"]
    assert task["mode"] in ("t2v", "i2v")
    assert task["steps"] == 4 and task["cfg"] == 1.0

    files = {"clip": ("out.mp4", b"\x00\x00fakevideo", "video/mp4")}
    data = {"worker_key": "wk1", "job_id": str(task["job_id"])}
    done = client.post("/api/worker/complete", data=data, files=files)
    assert done.status_code == 200

    prog = client.get(f"/api/projects/{proj['id']}/progress").json()
    assert prog["done"] == 1 and prog["pct"] == 100.0


def test_models_endpoint_exposes_caps(client):
    models = client.get("/api/models").json()
    assert any(m["model_id"] == "wan22_a14b" for m in models)
    wan = next(m for m in models if m["model_id"] == "wan22_a14b")
    assert wan["supports_i2v"] and wan["steps"] == 4
