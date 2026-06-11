"""Cards slot decorator activity for the central play area."""

import pygame

from activities.visible_cards_hand_activity import VisibleCardsHandDecorator
from game_screen import debug_overlay


class CardsSlotActivityDecorator(VisibleCardsHandDecorator):
    """Temporary table slot decorator; Controller will provide real table cards."""

    def __init__(self, hand_activity, cards=None, resource_manager=None, max_cards=2):
        self.validate_slot_hand_activity(hand_activity)
        super().__init__(
            hand_activity,
            cards=cards,
            resource_manager=resource_manager,
            max_cards=max_cards,
        )
        self.slot_content_local_rect = pygame.Rect(0, 0, 0, 0)
        self.slot_content_scaled_local_rect = pygame.Rect(0, 0, 0, 0)
        self._last_slot_layout_signature = None

    @staticmethod
    def validate_slot_hand_activity(hand_activity):
        frame = getattr(hand_activity, "frame", None)
        if frame is None or not callable(getattr(frame, "move_group_local", None)):
            raise TypeError("CardsSlotActivityDecorator requires hand_activity.frame.move_group_local()")

    def apply_fixture(self, fixture):
        super().apply_fixture(fixture)
        self.normalize_slot_content(force=True)

    def update(self, dt):
        super().update(dt)
        self.normalize_slot_content()

    def set_cards(self, cards, force=False):
        super().set_cards(cards, force=force)
        self.normalize_slot_content(force=True)

    def get_slot_content_rect(self):
        """Return visible occupied card bounds in slot frame-local coordinates."""
        return self.get_slot_content_scaled_local_rect()

    def get_slot_content_unscaled_local_rect(self):
        """Return occupied card bounds before card scale is applied."""
        return self.slot_content_local_rect.copy()

    def get_slot_content_scaled_local_rect(self):
        """Return occupied card bounds after card scale is applied."""
        return self.slot_content_scaled_local_rect.copy()

    def get_slot_content_screen_rect(self):
        """Return occupied visible card bounds in screen coordinates."""
        bounds = self.calculate_generated_groups_screen_bounds()
        if bounds is None:
            return pygame.Rect(0, 0, 0, 0)
        return bounds

    def draw_debug_overlay(self, screen):
        if not debug_overlay.should_draw_activity_rect():
            return
        rect = self.get_slot_content_screen_rect()
        if rect.width > 0 and rect.height > 0:
            pygame.draw.rect(screen, (255, 232, 64), rect, 2)

    def normalize_slot_content(self, force=False):
        """Compatibility alias for older callers."""
        signature = self.get_slot_layout_signature()
        if not force and signature == self._last_slot_layout_signature:
            return
        self.move_generated_groups_to_slot_origin()
        self._last_slot_layout_signature = self.get_slot_layout_signature()

    def get_slot_layout_signature(self):
        return tuple(
            (
                group.id,
                tuple(group.local_rect),
                1.0 if group.scale_factor is None else group.scale_factor,
            )
            for group in self.iter_generated_groups()
        )

    def move_generated_groups_to_slot_origin(self):
        """Move generated groups so their local bounds start at the slot origin."""
        bounds = self.calculate_generated_groups_local_bounds()
        if bounds is None:
            self.slot_content_local_rect = pygame.Rect(0, 0, 0, 0)
            self.slot_content_scaled_local_rect = pygame.Rect(0, 0, 0, 0)
            return

        for group in self.iter_generated_groups():
            rect = group.local_rect
            self.hand_activity.frame.move_group_local(
                group,
                (rect.x - bounds.x, rect.y - bounds.y),
            )

        self.slot_content_local_rect = pygame.Rect(0, 0, bounds.width, bounds.height)
        scaled_bounds = self.calculate_generated_groups_scaled_local_bounds()
        self.slot_content_scaled_local_rect = (
            scaled_bounds.copy()
            if scaled_bounds is not None
            else pygame.Rect(0, 0, 0, 0)
        )

    def calculate_generated_groups_local_bounds(self):
        bounds = None
        for group in self.iter_generated_groups():
            rect = self.get_group_slot_local_rect(group)
            bounds = rect.copy() if bounds is None else bounds.union(rect)
        return bounds

    def calculate_generated_groups_scaled_local_bounds(self):
        bounds = None
        for group in self.iter_generated_groups():
            rect = self.get_group_slot_scaled_local_rect(group)
            bounds = rect.copy() if bounds is None else bounds.union(rect)
        return bounds

    def calculate_generated_groups_screen_bounds(self):
        bounds = None
        for group in self.iter_generated_groups():
            rect = group.rect
            bounds = rect.copy() if bounds is None else bounds.union(rect)
        return bounds

    @staticmethod
    def get_group_slot_local_rect(group):
        return group.local_rect.copy()

    @staticmethod
    def get_group_slot_scaled_local_rect(group):
        if hasattr(group, "get_scaled_local_rect"):
            return group.get_scaled_local_rect()
        return group.local_rect.copy()
