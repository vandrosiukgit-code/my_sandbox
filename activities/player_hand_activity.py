"""Interactive player hand activity with player-specific fan geometry."""

from dataclasses import dataclass
import math

import pygame

from activities.bot_hand_activity import BotHandActivity
from activities.cards_slot_activity import CardsSlotActivityDecorator
from activities.visible_cards_hand_activity import VisibleCardsHandDecorator


@dataclass(frozen=True)
class FanGeometry:
    center_x: int
    center_y: int
    half_span: float
    max_angle: float
    radius: float | None


class PlayerHandActivity(BotHandActivity):
    """Visible player hand geometry separated from bot hand geometry.

    Bot hands are mostly decorative. The bottom player's hand is interactive,
    so its fan favors predictable horizontal hit areas over a compact circular
    arc. It still creates the same visual-only card groups as BotHandActivity.
    """

    def __init__(
        self,
        *args,
        max_card_angle=45,
        edge_padding_ratio=0.02,
        fan_width_ratio=0.95,
        sector_angle_extra=0,
        use_stable_reference_fan=False,
        **kwargs,
    ):
        normalized_max_card_angle = self.normalize_non_negative_float(
            max_card_angle,
            "max_card_angle",
            maximum=90.0,
        )
        super().__init__(*args, max_total_angle=normalized_max_card_angle * 2, **kwargs)
        self.set_max_card_angle(normalized_max_card_angle)
        self.edge_padding_ratio = self.normalize_ratio(
            edge_padding_ratio,
            "edge_padding_ratio",
            maximum=0.45,
        )
        self.fan_width_ratio = self.normalize_ratio(
            fan_width_ratio,
            "fan_width_ratio",
            maximum=1.0,
        )
        self.sector_angle_extra = self.normalize_non_negative_float(
            sector_angle_extra,
            "sector_angle_extra",
            maximum=90.0,
        )
        self.use_stable_reference_fan = bool(use_stable_reference_fan)
        self.fan_area_local_rect = None

    def set_fan_area_local_rect(self, rect):
        """Set explicit frame-local layout area for the player hand fan."""
        if rect is None:
            self.fan_area_local_rect = None
            return
        self.fan_area_local_rect = self.frame.round_rect(rect)

    def apply_fixture(self, fixture):
        if not fixture:
            return

        self.set_max_card_angle(
            self.normalize_non_negative_float(
                fixture.get("max_card_angle", self.max_card_angle),
                "max_card_angle",
                maximum=90.0,
            )
        )
        self.edge_padding_ratio = self.normalize_ratio(
            fixture.get("edge_padding_ratio", self.edge_padding_ratio),
            "edge_padding_ratio",
            maximum=0.45,
        )
        self.fan_width_ratio = self.normalize_ratio(
            fixture.get("fan_width_ratio", self.fan_width_ratio),
            "fan_width_ratio",
            maximum=1.0,
        )
        self.sector_angle_extra = self.normalize_non_negative_float(
            fixture.get("sector_angle_extra", self.sector_angle_extra),
            "sector_angle_extra",
            maximum=90.0,
        )
        self.use_stable_reference_fan = bool(
            fixture.get("use_stable_reference_fan", self.use_stable_reference_fan)
        )

        super().apply_fixture(fixture)

    def set_max_card_angle(self, value):
        self.max_card_angle = self.normalize_non_negative_float(
            value,
            "max_card_angle",
            maximum=90.0,
        )
        self.max_total_angle = self.max_card_angle * 2

    def apply_fan_layout(self):
        """Lay cards out as an interactive bottom-hand arc.

        Card centers are placed on the middle arc of the hand sector. Each
        card's long axis follows the radial ray from the sector center.
        """
        count = len(self.generated_groups)
        if count <= 0:
            self._last_layout_signature = self.get_layout_signature()
            return

        geometry = self.calculate_fan_geometry()

        for index, group in enumerate(self.generated_groups):
            slot = self.calculate_slot_position(index, count)
            local_angle = slot * geometry.max_angle

            center_position = self.calculate_center_arc_position(local_angle, geometry)

            self.apply_card_center_transform(
                group,
                self.orientation_degrees + local_angle,
                center_position,
            )
        self._last_layout_signature = self.get_layout_signature()

    def get_layout_signature(self):
        return (
            super().get_layout_signature(),
            self.max_card_angle,
            self.edge_padding_ratio,
            self.fan_width_ratio,
            self.sector_angle_extra,
            self.use_stable_reference_fan,
            None if self.fan_area_local_rect is None else tuple(self.fan_area_local_rect),
        )

    def calculate_fan_geometry(self):
        """Calculate all fan geometry from frame size, density, and max angle."""
        frame_rect = self.get_fan_area_local_rect()

        padding = self.calculate_edge_padding(frame_rect)
        left_bound = frame_rect.left + padding
        right_bound = frame_rect.right - padding
        card_half_width = self.get_card_local_half_width()

        center_x, center_y = self.get_fan_center(frame_rect)
        center_x = max(
            left_bound + card_half_width,
            min(right_bound - card_half_width, center_x),
        )
        half_span = max(
            0,
            min(center_x - left_bound, right_bound - center_x) - card_half_width,
        )

        half_span *= self.fan_width_ratio

        radius = self.calculate_center_arc_radius(frame_rect)
        max_angle = 0.0
        if radius > 0 and half_span > 0:
            max_angle = math.degrees(math.asin(max(-1.0, min(1.0, half_span / radius))))
            max_angle += self.sector_angle_extra / 2
            max_angle = min(max_angle, abs(float(self.max_card_angle)))

        if max_angle < 0.5:
            radius = None

        return FanGeometry(
            center_x=center_x,
            center_y=center_y,
            half_span=half_span,
            max_angle=max_angle,
            radius=radius,
        )

    def get_fan_area_local_rect(self):
        if self.fan_area_local_rect is None:
            return self.frame.content_rect
        return self.fan_area_local_rect.copy()

    def apply_card_center_transform(self, group, angle_degrees, center_position):
        """Rotate a card and place its rectangle center on the fan center arc."""
        base_surface = self.group_base_frames[group.id][0]
        rotated_surface = self.rotate_card_surface(base_surface, angle_degrees)

        group.set_primary_layer_frames([rotated_surface], position=(0, 0))
        group.set_scale_factor(self.scale_factor)
        group.set_local_rect((0, 0, rotated_surface.get_width(), rotated_surface.get_height()))
        self.frame.place_group_center_local(group, center_position)

    @staticmethod
    def rotate_card_surface(surface, angle_degrees):
        return pygame.transform.rotate(surface, -angle_degrees)

    @staticmethod
    def calculate_center_arc_position(angle_degrees, geometry):
        radius = geometry.radius
        if radius is None:
            return geometry.center_x, geometry.center_y
        radians = math.radians(angle_degrees)
        return (
            int(round(geometry.center_x + radius * math.sin(radians))),
            int(round(geometry.center_y - radius * math.cos(radians))),
        )

    def calculate_edge_padding(self, frame_rect):
        return max(0, int(round(frame_rect.width * self.edge_padding_ratio)))

    def get_card_local_half_width(self):
        return max(
            (frames[0].get_width() / 2 for frames in self.group_base_frames.values() if frames),
            default=0.0,
        )

    def get_fan_center(self, frame_rect):
        """Return sector center for the bottom-hand middle arc."""
        local_scale = self.get_activity_local_scale()
        radius = self.calculate_center_arc_radius(frame_rect)
        card_half_height = self.get_card_local_half_height()
        return (
            frame_rect.centerx + int(round(self.center_offset[0] * local_scale)),
            frame_rect.top
            + int(round(card_half_height + radius))
            + int(round(self.center_offset[1] * local_scale)),
        )

    def calculate_center_arc_radius(self, frame_rect):
        card_half_width = self.get_card_local_half_width()
        card_half_height = self.get_card_local_half_height()
        half_span = max(0.0, frame_rect.width / 2 - self.calculate_edge_padding(frame_rect) - card_half_width)
        sagitta = max(1.0, frame_rect.height - card_half_height * 2)
        return (half_span * half_span + sagitta * sagitta) / (2 * sagitta)

    def get_card_local_half_height(self):
        return max(
            (frames[0].get_height() / 2 for frames in self.group_base_frames.values() if frames),
            default=0.0,
        )

    def calculate_slot_position(self, index, count):
        """Return one of count evenly spaced sector rays, assigned center-out."""
        if count <= 1:
            return 0.0
        return self.calculate_dense_slot_position(index, count)

    @staticmethod
    def calculate_dense_slot_position(index, count):
        """Return one of count evenly spaced sector rays, assigned center-out."""
        slots = [
            -1.0 + 2.0 * slot_index / (count - 1)
            for slot_index in range(count)
        ]
        center_out_slots = sorted(slots, key=lambda slot: (abs(slot), -slot))
        return center_out_slots[index]

    @staticmethod
    def calculate_arc_y(angle_degrees, geometry):
        radius = geometry.radius

        if radius is None:
            return 0

        return -radius * math.cos(math.radians(angle_degrees))

    def draw(self, screen):
        """Draw debug overlays for this activity; groups are drawn by GameScreen."""
        _ = screen

    def iter_generated_groups(self):
        """Return generated hand groups in draw order."""
        return self.iter_groups_in_draw_order()

    def iter_groups_in_draw_order(self):
        return tuple(sorted(self.generated_groups, key=self.get_group_draw_x))

    @staticmethod
    def get_group_draw_x(group):
        return group.local_rect.centerx

    @staticmethod
    def normalize_ratio(value, name, maximum=None):
        value = float(value)
        if value < 0:
            raise ValueError(f"{name} must be non-negative: {value!r}")
        if maximum is not None and value > maximum:
            raise ValueError(f"{name} must be <= {maximum}: {value!r}")
        return value

    @staticmethod
    def normalize_non_negative_float(value, name, maximum=None):
        value = float(value)
        if value < 0:
            raise ValueError(f"{name} must be non-negative: {value!r}")
        if maximum is not None and value > maximum:
            raise ValueError(f"{name} must be <= {maximum}: {value!r}")
        return value


__all__ = [
    "CardsSlotActivityDecorator",
    "PlayerHandActivity",
    "VisibleCardsHandDecorator",
]
