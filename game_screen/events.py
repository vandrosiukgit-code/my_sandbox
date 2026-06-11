"""Screen/controller boundary payloads.

GameScreen converts raw pygame events into ScreenInputEvent objects.
GameController interprets them, mutates game state, and can return
VisualCommand objects for the screen visual layer.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FrameHit:
    """Result of hit-testing a point against screen frames and groups."""

    frame_id: str | None
    group_id: str | None
    screen_pos: tuple[int, int]
    local_pos: tuple[int, int] | None = None


@dataclass(frozen=True)
class ScreenInputEvent:
    """Normalized input event sent from GameScreen to GameController."""

    type: str
    button: str | None = None
    group_id: str | None = None
    frame_id: str | None = None
    screen_pos: tuple[int, int] | None = None
    local_pos: tuple[int, int] | None = None
    payload: dict = field(default_factory=dict)
    raw_event: object | None = None


@dataclass(frozen=True)
class VisualCommand:
    """Controller response that asks GameScreen to run a visual change."""

    type: str
    target: str | None = None
    value: object | None = None
    activity: str | None = None
    group_id: str | None = None
    from_frame: str | None = None
    to_frame: str | None = None
    payload: dict = field(default_factory=dict)


