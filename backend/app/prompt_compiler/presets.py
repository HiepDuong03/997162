"""Cinematic preset phrase libraries — the 'Higgsfield moat' layer.

Each preset maps a short UI token to a natural-language fragment that Wan 2.2's
UMT5 text encoder responds well to. Keep fragments short and concrete.
"""

# ~30 camera movement / framing presets.
CAMERA_PRESETS: dict[str, str] = {
    "static": "static locked-off camera",
    "slow_push_in": "slow cinematic push-in, camera dollying forward",
    "push_in_fast": "fast dolly push-in toward the subject",
    "pull_out": "smooth dolly pull-out revealing the wider scene",
    "dolly_left": "camera dollying smoothly to the left",
    "dolly_right": "camera dollying smoothly to the right",
    "orbit_left": "camera orbiting around the subject counter-clockwise",
    "orbit_right": "camera orbiting around the subject clockwise",
    "crane_up": "crane shot rising upward",
    "crane_down": "crane shot descending downward",
    "tilt_up": "camera tilting upward",
    "tilt_down": "camera tilting downward",
    "pan_left": "camera panning to the left",
    "pan_right": "camera panning to the right",
    "crash_zoom": "sudden crash zoom onto the subject",
    "slow_zoom": "slow gradual zoom in",
    "handheld": "handheld camera with subtle natural shake",
    "steadicam_follow": "steadicam tracking shot following the subject",
    "tracking_side": "side tracking shot moving parallel to the subject",
    "low_angle": "dramatic low-angle shot looking up",
    "high_angle": "high-angle shot looking down",
    "birds_eye": "top-down bird's-eye view",
    "dutch_angle": "tilted dutch-angle framing",
    "over_shoulder": "over-the-shoulder shot",
    "close_up": "tight close-up shot",
    "extreme_close_up": "extreme close-up",
    "medium_shot": "medium shot framing the subject from the waist up",
    "wide_shot": "wide establishing shot",
    "aerial_drone": "sweeping aerial drone shot",
    "fpv_drone": "dynamic FPV drone fly-through",
    "rack_focus": "rack focus shifting focus between foreground and background",
}

# Subject motion presets.
MOTION_PRESETS: dict[str, str] = {
    "none": "",
    "idle": "standing still, subtle idle motion, breathing",
    "walking": "walking forward at a steady pace",
    "walking_toward": "walking toward the camera",
    "walking_away": "walking away from the camera",
    "running": "running dynamically",
    "turning": "turning to look",
    "sitting_down": "sitting down slowly",
    "standing_up": "standing up",
    "gesturing": "gesturing expressively while speaking",
    "looking_around": "looking around, scanning the environment",
    "reaching": "reaching out with one hand",
    "dancing": "dancing rhythmically",
    "fighting": "dynamic fighting motion",
    "riding": "riding forward",
    "flying": "flying through the air",
    "falling": "falling downward",
    "waving": "waving a hand",
}

DEFAULT_QUALITY_SUFFIX = (
    "cinematic lighting, highly detailed, sharp focus, film grain, "
    "professional color grading, 4k, masterpiece"
)

DEFAULT_NEGATIVE = (
    "blurry, low quality, distorted, deformed, extra limbs, extra fingers, "
    "watermark, text, jpeg artifacts, oversaturated, flickering, morphing, "
    "static image, still frame"
)
