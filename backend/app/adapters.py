"""Model adapter registry — loads capability manifests from adapters/*.json."""
import json
import os
from functools import lru_cache

ADAPTERS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "adapters"))


@lru_cache(maxsize=1)
def load_all() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for fn in os.listdir(ADAPTERS_DIR):
        if fn.endswith(".json"):
            with open(os.path.join(ADAPTERS_DIR, fn), "r", encoding="utf-8") as f:
                m = json.load(f)
                out[m["model_id"]] = m
    return out


def get(model_id: str) -> dict:
    m = load_all()
    if model_id not in m:
        raise KeyError(f"unknown model_id: {model_id}")
    return m[model_id]


def resolve_resolution(model_id: str, vram_gb: float) -> tuple[str, int, int]:
    """Pick the best resolution the given GPU can run for this model."""
    m = get(model_id)
    best = None
    for name, r in m["resolutions"].items():
        if vram_gb >= r["min_vram_gb"]:
            if best is None or r["width"] * r["height"] > best[1] * best[2]:
                best = (name, r["width"], r["height"])
    if best is None:
        r = m["resolutions"][m["default_resolution"]]
        return m["default_resolution"], r["width"], r["height"]
    return best
