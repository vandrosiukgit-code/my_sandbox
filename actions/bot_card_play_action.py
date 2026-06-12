"""Visual action for moving one bot card geometry to a table slot geometry."""

from dataclasses import dataclass

import pygame

from actions.base_action import Action
from animations.base_animation import Animation
from animations.easing import ease_out_quad, lerp_float
from core.resource import ResourceManager
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


class BotCardPlayAction(Action):
    """Finite visual step for a visual-only card flight rectangle."""

    MIN_FLIP_WIDTH_RATIO = 0.08
    FLIP_PHASE_RATIO = 2 / 3

    def __init__(
        self,
        from_geometry,
        to_geometry,
        back_resource_key,
        face_resource_key,
        duration=0.35,
        group_id="bot_turn.flight_card",
        cleanup_group=None,
        resource_manager=ResourceManager,
    ):
        self.from_geometry = CardFlightGeometry.from_value(from_geometry)
        self.to_geometry = CardFlightGeometry.from_value(to_geometry)
        self.resource_manager = resource_manager
        self.back_surface = self.get_resource_surface(back_resource_key)
        self.face_surface = self.get_resource_surface(face_resource_key)
        self.group = self.create_flight_group(group_id, self.from_geometry, self.back_surface)
        self.cleanup_group = cleanup_group
        super().__init__(
            group_ids=(self.group.id,),
            animations=(
                CardFlightGeometryAnimation(
                    group=self.group,
                    from_geometry=self.from_geometry,
                    to_geometry=self.to_geometry,
                    duration=duration,
                    on_finish=self.finish_bot_card_move,
                    back_surface=self.back_surface,
                    face_surface=self.face_surface,
                    min_flip_width_ratio=self.MIN_FLIP_WIDTH_RATIO,
                    flip_phase_ratio=self.FLIP_PHASE_RATIO,
                ),
            ),
        )

    @classmethod
    def create_flight_group(cls, group_id, geometry, back_surface):
        surface = cls.render_surface(
            geometry.size,
            geometry.angle_degrees,
            back_surface,
        )
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
    def render_surface(size, angle_degrees, texture_surface, flip_width_ratio=1.0):
        base_surface = pygame.Surface(size, pygame.SRCALPHA)
        visible_width = max(1, int(round(size[0] * flip_width_ratio)))
        visible_surface = pygame.transform.smoothscale(texture_surface, (visible_width, size[1]))
        visible_rect = visible_surface.get_rect(center=base_surface.get_rect().center)
        base_surface.fill((0, 0, 0, 0))
        base_surface.blit(visible_surface, visible_rect)
        return pygame.transform.rotate(base_surface, -angle_degrees)

    def get_resource_surface(self, resource_key):
        frames = self.resource_manager.get_frames(resource_key)
        if not frames:
            raise KeyError(f"Card flight resource has no frames: {resource_key!r}")
        return frames[0].copy()

    def finish_bot_card_move(self, _animation):
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
        back_surface=None,
        face_surface=None,
        min_flip_width_ratio=BotCardPlayAction.MIN_FLIP_WIDTH_RATIO,
        flip_phase_ratio=BotCardPlayAction.FLIP_PHASE_RATIO,
    ):
        super().__init__(duration=duration, on_finish=on_finish, max_frame_dt=1 / 120)
        self.group = group
        self.from_geometry = CardFlightGeometry.from_value(from_geometry)
        self.to_geometry = CardFlightGeometry.from_value(to_geometry)
        self.back_surface = self.normalize_surface(back_surface, "back_surface")
        self.face_surface = self.normalize_surface(face_surface, "face_surface")
        self.min_flip_width_ratio = float(min_flip_width_ratio)
        self.flip_phase_ratio = max(0.01, min(0.99, float(flip_phase_ratio)))

    def start(self):
        super().start()
        self.apply(0.0)

    def apply(self, progress):
        move_progress = ease_out_quad(progress)
        flip_progress = ease_out_quad(self.get_flip_progress(progress))
        geometry = self.interpolate_geometry(move_progress)
        surface = BotCardPlayAction.render_surface(
            geometry.size,
            geometry.angle_degrees,
            self.get_card_side_surface(flip_progress),
            self.get_flip_width_ratio(flip_progress),
        )
        rect = surface.get_rect(center=geometry.center)
        self.group.set_rect(rect)
        self.group.set_primary_layer_frames([surface], position=(0, 0))

    def get_card_side_surface(self, progress):
        if progress < 0.5:
            return self.back_surface
        return self.face_surface

    def get_flip_width_ratio(self, progress):
        distance_from_midpoint = abs(progress - 0.5) * 2.0
        return max(self.min_flip_width_ratio, distance_from_midpoint)

    def get_flip_progress(self, progress):
        if progress >= self.flip_phase_ratio:
            return 1.0
        return progress / self.flip_phase_ratio

    @staticmethod
    def normalize_surface(surface, name):
        if not isinstance(surface, pygame.Surface):
            raise TypeError(f"{name} must be pygame.Surface: {surface!r}")
        return surface.copy()


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
