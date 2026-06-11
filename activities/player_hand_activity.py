"""Interactive player hand activity with player-specific fan geometry."""

from dataclasses import dataclass
import math

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

        Cards are distributed along a shallow arc and rotated by their position
        on that arc. This keeps the hand readable while leaving broad visible
        hit zones for CardSelectionActivity.
        """
        count = len(self.generated_groups)
        if count <= 0:
            self._last_layout_signature = self.get_layout_signature()
            return

        geometry = self.calculate_fan_geometry()

        for index, group in enumerate(self.generated_groups):
            slot = self.calculate_slot_position(index, count)
            local_angle = slot * geometry.max_angle

            pivot_position = (
                int(round(geometry.center_x + slot * geometry.half_span)),
                int(
                    round(
                        geometry.center_y
                        + self.calculate_arc_y(local_angle, geometry)
                    )
                ),
            )

            self.apply_card_transform(
                group,
                self.orientation_degrees + local_angle,
                pivot_position,
            )
        self._last_layout_signature = self.get_layout_signature()

    def get_layout_signature(self):
        return (
            super().get_layout_signature(),
            self.max_card_angle,
            self.edge_padding_ratio,
            self.fan_width_ratio,
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
        available_half_span = max(
            0,
            min(center_x - left_bound, right_bound - center_x) - card_half_width,
        )

        half_span = available_half_span * self.fan_width_ratio

        max_angle = abs(float(self.max_card_angle))
        angle_radians = math.radians(max_angle)

        radius = None
        min_angle_radians = math.radians(0.5)
        if half_span > 0 and angle_radians >= min_angle_radians:
            radius = half_span / math.sin(angle_radians)

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

    def calculate_edge_padding(self, frame_rect):
        return max(0, int(round(frame_rect.width * self.edge_padding_ratio)))

    def get_card_local_half_width(self):
        return max(
            (group.local_rect.width / 2 for group in self.generated_groups),
            default=0.0,
        )

    def get_fan_center(self, frame_rect):
        """Return bottom-hand baseline center in frame-local coordinates."""
        local_scale = self.get_activity_local_scale()
        return (
            frame_rect.centerx + int(round(self.center_offset[0] * local_scale)),
            frame_rect.bottom + int(round(self.center_offset[1] * local_scale)),
        )

    def calculate_slot_position(self, index, count):
        """Return a compact normalized slot centered around the fan middle."""
        if count <= 1:
            return 0.0

        if self.use_stable_reference_fan:
            reference_count = max(count, self.reference_card_count)
        else:
            reference_count = count
        max_slot_offset = max(1.0, (reference_count - 1) / 2)
        slot_offset = index - (count - 1) / 2

        return max(-1.0, min(1.0, slot_offset / max_slot_offset))

    @staticmethod
    def calculate_arc_y(angle_degrees, geometry):
        radius = geometry.radius

        if radius is None:
            return 0

        return -radius * (1 - math.cos(math.radians(angle_degrees)))

    def draw(self, screen):
        """Draw debug overlays for this activity; groups are drawn by GameScreen."""
        _ = screen

    def iter_generated_groups(self):
        """Return generated hand groups in draw order."""
        return self.iter_groups_in_draw_order()

    def iter_groups_in_draw_order(self):
        return tuple(self.generated_groups)

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
