"""Seed a chained-mode scene into a running backend for manual/mock-worker E2E."""
import sys
import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8011"

ch = requests.post(f"{BASE}/api/characters", json={"name": "Elara", "appearance": "red coat, black hair"}).json()
sr = requests.post(f"{BASE}/api/scene-refs", json={"name": "Forest", "environment": "foggy forest", "lighting": "golden hour"}).json()
proj = requests.post(f"{BASE}/api/projects", json={"name": "E2E Demo"}).json()
scene = requests.post(f"{BASE}/api/scenes", json={
    "project_id": proj["id"], "name": "S1", "scene_ref_id": sr["id"],
    "consistency_mode": "chained",
}).json()
for i in range(3):
    requests.post(f"{BASE}/api/shots", json={
        "scene_id": scene["id"], "order": i,
        "action_text": f"walks forward step {i}",
        "camera_preset": "slow_push_in", "motion_preset": "walking",
        "character_ids": str(ch["id"]),
    })
r = requests.post(f"{BASE}/api/scenes/{scene['id']}/render").json()
print("enqueued", r)
print("project_id", proj["id"])
