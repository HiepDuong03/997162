from app.prompt_compiler import (
    CharacterInput,
    SceneInput,
    ShotInput,
    compile_prompt,
)


def test_priority_order_action_first():
    out = compile_prompt(
        ShotInput(
            action_text="opens a wooden door",
            motion_preset="walking",
            camera_preset="slow_push_in",
            characters=[CharacterInput(name="Elara", appearance="red coat, black hair")],
            scene=SceneInput(environment="foggy forest", lighting="golden hour"),
        )
    )
    p = out.prompt
    # action must appear before character, scene, camera
    assert p.index("opens a wooden door") < p.index("Elara")
    assert p.index("Elara") < p.index("foggy forest")
    assert p.index("foggy forest") < p.index("push-in")


def test_dedup_and_negative_merge():
    out = compile_prompt(
        ShotInput(
            action_text="stands still",
            characters=[CharacterInput(name="A", negative_prompt="ugly")],
            scene=SceneInput(negative_prompt="ugly, dark"),
        )
    )
    # "ugly" should not be duplicated in the negative
    assert out.negative.lower().count("ugly") == 1


def test_unknown_camera_falls_back_to_literal():
    out = compile_prompt(ShotInput(action_text="x", camera_preset="my_custom_move"))
    assert "my_custom_move" in out.prompt
