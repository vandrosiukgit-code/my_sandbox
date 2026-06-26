"""Screen/controller boundary payloads.

GameScreen converts raw pygame events into ScreenInputEvent objects.
GameController interprets them, mutates game state, and can return
VisualCommand objects for the screen visual layer.
"""

from dataclasses import dataclass, field
from typing import Protocol


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
    command_id: str | None = None
    blocking: bool = True

    def __post_init__(self):
        if not isinstance(self.type, str) or not self.type:
            raise ValueError("VisualCommand.type must be a non-empty string")
        if not isinstance(self.payload, dict):
            raise TypeError("VisualCommand.payload must be a dict")


@dataclass(frozen=True)
class ActivityResult:
    """Visual activity completion fact returned to GameController through GameScreen."""

    type: str
    source: str
    command_id: str | None = None
    payload: dict = field(default_factory=dict)
    status: str = "completed"

    def __post_init__(self):
        if not isinstance(self.type, str) or not self.type:
            raise ValueError("ActivityResult.type must be a non-empty string")
        if not isinstance(self.source, str) or not self.source:
            raise ValueError("ActivityResult.source must be a non-empty string")
        if not isinstance(self.payload, dict):
            raise TypeError("ActivityResult.payload must be a dict")
        if self.status not in ("completed", "cancelled", "failed"):
            raise ValueError("ActivityResult.status must be completed, cancelled, or failed")


@dataclass(frozen=True)
class ControllerResponse:
    """Standard GameController response consumed by GameScreen."""

    commands: tuple[VisualCommand, ...] = ()
    state_view: object | None = None

    def __post_init__(self):
        commands = tuple(self.commands or ())
        for command in commands:
            if not isinstance(command, VisualCommand):
                raise TypeError("ControllerResponse.commands must contain VisualCommand objects")
        object.__setattr__(self, "commands", commands)


class GameControllerProtocol(Protocol):
    """Screen-facing controller contract.

    Activities report results to GameScreen. GameScreen is responsible for
    calling this protocol and dispatching returned visual commands.
    """

    def start_game(self) -> ControllerResponse:
        ...

    def handle_input(self, input_event: ScreenInputEvent) -> ControllerResponse:
        ...

    def handle_player_action(self, action) -> ControllerResponse:
        ...

    def handle_activity_result(self, result: ActivityResult) -> ControllerResponse:
        ...

    def get_state_view(self):
        ...


