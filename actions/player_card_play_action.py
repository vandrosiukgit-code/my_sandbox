"""Visual action for moving one player card geometry to a table slot geometry."""

from dataclasses import dataclass

import pygame

from actions.base_action import Action
from animations.base_animation import Animation
from animations.easing import ease_out_quad, lerp_float
from group.group import Group, Layer


@dataclass(frozen=True)
class CardFlightGeometry:
    """Screen-space card geometry used by card flight animation."""

    center: tuple[int, int]
    size: tuple[int, int]
    angle_degrees: float = 0.0

    @classmethod
    def from_value(cls, value):
        if isinstance(value, cls):
            return value
        if not isinstance(value, dict):
            raise TypeError(f"CardFlightGeometry requires dict or CardFlightGeometry: {value!r}")
        return cls(
            center=cls.normalize_pair(value["center"], "center"),
            size=cls.normalize_size(value["size"]),
            angle_degrees=float(value.get("angle_degrees", 0.0)),
        )

    @staticmethod
    def normalize_pair(value, name):
        if not isinstance(value, (tuple, list)) or len(value) < 2:
            raise TypeError(f"{name} must be a pair: {value!r}")
        return int(round(float(value[0]))), int(round(float(value[1])))

    @staticmethod
    def normalize_size(value):
        width, height = CardFlightGeometry.normalize_pair(value, "size")
        return max(1, width), max(1, height)


class PlayerCardPlayAction(Action):
    """Finite visual step for a visual-only lower-player card flight rectangle."""

    BROWN = (104, 55, 28, 255)

    def __init__(
        self,
        from_geometry,
        to_geometry,
        duration=0.35,
        group_id="player_turn.flight_card",
        cleanup_group=None,
    ):
        self.from_geometry = CardFlightGeometry.from_value(from_geometry)
        self.to_geometry = CardFlightGeometry.from_value(to_geometry)
        self.group = self.create_flight_group(group_id, self.from_geometry)
        self.cleanup_group = cleanup_group
        super().__init__(
            group_ids=(self.group.id,),
            animations=(
                CardFlightGeometryAnimation(
                    group=self.group,
                    from_geometry=self.from_geometry,
                    to_geometry=self.to_geometry,
                    duration=duration,
                    on_finish=self.finish_player_card_move,
                    color=self.BROWN,
                ),
            ),
        )

    @classmethod
    def create_flight_group(cls, group_id, geometry):
        surface = cls.render_surface(geometry.size, geometry.angle_degrees, cls.BROWN)
        rect = surface.get_rect(center=geometry.center)
        return Group(
            group_id=group_id,
            rect=rect,
            layers=[
                Layer(
                    name="card",
                    frames=[surface],
                    layer_type="surface",
                )
            ],
        )

    @staticmethod
    def render_surface(size, angle_degrees, color):
        base_surface = pygame.Surface(size, pygame.SRCALPHA)
        base_surface.fill(color)
        return pygame.transform.rotate(base_surface, -angle_degrees)

    def finish_player_card_move(self, _animation):
        self.cleanup_flight_group()

    def cleanup_flight_group(self):
        if callable(self.cleanup_group):
            self.cleanup_group(self.group)


class CardFlightGeometryAnimation(Animation):
    """Animate a generated card rectangle through screen-space geometry."""

    animated_properties = ("screen_geometry",)
    coordinate_space = "screen"

    def __init__(
        self,
        group,
        from_geometry,
        to_geometry,
        duration=0.35,
        on_finish=None,
        color=PlayerCardPlayAction.BROWN,
    ):
        super().__init__(duration=duration, on_finish=on_finish)
        self.group = group
        self.from_geometry = CardFlightGeometry.from_value(from_geometry)
        self.to_geometry = CardFlightGeometry.from_value(to_geometry)
        self.color = color

    def start(self):
        super().start()
        self.apply(0.0)

    def apply(self, progress):
        progress = ease_out_quad(progress)
        geometry = self.interpolate_geometry(progress)
        surface = PlayerCardPlayAction.render_surface(
            geometry.size,
            geometry.angle_degrees,
            self.color,
        )
        rect = surface.get_rect(center=geometry.center)
        self.group.set_rect(rect)
        self.group.set_primary_layer_frames([surface], position=(0, 0))

    def interpolate_geometry(self, progress):
        return CardFlightGeometry(
            center=(
                int(round(lerp_float(self.from_geometry.center[0], self.to_geometry.center[0], progress))),
                int(round(lerp_float(self.from_geometry.center[1], self.to_geometry.center[1], progress))),
            ),
            size=(
                max(1, int(round(lerp_float(self.from_geometry.size[0], self.to_geometry.size[0], progress)))),
                max(1, int(round(lerp_float(self.from_geometry.size[1], self.to_geometry.size[1], progress)))),
            ),
            angle_degrees=lerp_float(
                self.from_geometry.angle_degrees,
                self.to_geometry.angle_degrees,
                progress,
            ),
        )
