"""Screen/controller boundary payloads.

GameScreen converts raw pygame events into ScreenInputEvent objects.
GameController interprets them, mutates game state, and can return
VisualCommand objects for the screen visual layer.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ZoneHit:
    """Result of hit-testing a point against screen zones and actors."""

    zone_id: str | None
    actor_id: str | None
    screen_pos: tuple[int, int]
    local_pos: tuple[int, int] | None = None


@dataclass(frozen=True)
class ScreenInputEvent:
    """Normalized input event sent from GameScreen to GameController."""

    type: str
    button: str | None = None
    actor_id: str | None = None
    zone_id: str | None = None
    screen_pos: tuple[int, int] | None = None
    local_pos: tuple[int, int] | None = None
    raw_event: object | None = None


@dataclass(frozen=True)
class VisualCommand:
    """Controller response that asks GameScreen to run a visual change."""

    type: str
    actor_id: str | None = None
    from_zone: str | None = None
    to_zone: str | None = None
    payload: dict = field(default_factory=dict)
