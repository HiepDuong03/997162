"""Deterministic prompt compiler.

Merge order is TRUNCATION-SAFE for UMT5's token limit: the most important tokens
(action + character identity) come first so that if the encoder truncates the
tail, the survivors are still the semantically critical parts.

    [Action/Motion] + [Character appearance] + [Scene environment] + [Camera] + [Quality]
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .presets import (
    CAMERA_PRESETS,
    DEFAULT_NEGATIVE,
    DEFAULT_QUALITY_SUFFIX,
    MOTION_PRESETS,
)


@dataclass
class CharacterInput:
    name: str = ""
    appearance: str = ""
    prompt_template: str = ""
    negative_prompt: str = ""


@dataclass
class SceneInput:
    environment: str = ""
    lighting: str = ""
    style: str = ""
    time_of_day: str = ""
    color_palette: str = ""
    atmosphere: str = ""
    negative_prompt: str = ""


@dataclass
class ShotInput:
    action_text: str = ""
    camera_preset: str = "static"
    motion_preset: str = "none"
    characters: list[CharacterInput] = field(default_factory=list)
    scene: Optional[SceneInput] = None
    quality_suffix: str = DEFAULT_QUALITY_SUFFIX


@dataclass
class CompiledPrompt:
    prompt: str
    negative: str


def _clean(parts: list[str]) -> list[str]:
    seen: list[str] = []
    for p in parts:
        p = " ".join(p.split()).strip().strip(",").strip()
        if p and p.lower() not in {s.lower() for s in seen}:
            seen.append(p)
    return seen


def compile_prompt(shot: ShotInput) -> CompiledPrompt:
    motion = MOTION_PRESETS.get(shot.motion_preset, "")
    camera = CAMERA_PRESETS.get(shot.camera_preset, shot.camera_preset)

    # 1. Action + motion (highest priority — survives truncation)
    action_block = ", ".join(_clean([shot.action_text, motion]))

    # 2. Character identity
    char_bits: list[str] = []
    for c in shot.characters:
        bits = _clean([c.name, c.appearance, c.prompt_template])
        if bits:
            char_bits.append(", ".join(bits))
    character_block = "; ".join(char_bits)

    # 3. Scene / environment
    scene_block = ""
    if shot.scene:
        s = shot.scene
        scene_block = ", ".join(
            _clean([s.environment, s.lighting, s.time_of_day, s.color_palette, s.atmosphere, s.style])
        )

    # 4. Camera, 5. Quality
    ordered = _clean([action_block, character_block, scene_block, camera, shot.quality_suffix])
    prompt = ", ".join(ordered)

    # Negatives: merge defaults + per-character + per-scene, dedup per comma-token.
    neg_sources = [DEFAULT_NEGATIVE]
    for c in shot.characters:
        if c.negative_prompt:
            neg_sources.append(c.negative_prompt)
    if shot.scene and shot.scene.negative_prompt:
        neg_sources.append(shot.scene.negative_prompt)
    neg_tokens: list[str] = []
    for src in neg_sources:
        neg_tokens.extend(src.split(","))
    negative = ", ".join(_clean(neg_tokens))

    return CompiledPrompt(prompt=prompt, negative=negative)
