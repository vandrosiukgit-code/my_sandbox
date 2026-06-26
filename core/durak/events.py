"""Domain events emitted by the isolated Durak controller."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GameEvent:
    type: str
    payload: dict
