"""Cards slot decorator activity for the central play area."""

import pygame

from activities.visible_cards_hand_activity import VisibleCardsHandDecorator


class CardsSlotActivityDecorator(VisibleCardsHandDecorator):
    """Temporary table slot decorator; Controller will provide real table cards."""

    def __init__(self, hand_activity, cards=None, resource_manager=None, max_cards=2):
        super().__init__(
            hand_activity,
            cards=cards,
            resource_manager=resource_manager,
            max_cards=max_cards,
        )
        self.validate_slot_hand_activity(hand_activity)
        self.slot_content_local_rect = pygame.Rect(0, 0, 0, 0)

    @staticmethod
    def validate_slot_hand_activity(hand_activity):
        frame = getattr(hand_activity, "frame", None)
        if frame is None or not callable(getattr(frame, "move_group_local", None)):
            raise TypeError("CardsSlotActivityDecorator requires hand_activity.frame.move_group_local()")

    def apply_fixture(self, fixture):
        super().apply_fixture(fixture)
        self.move_generated_groups_to_slot_origin()

    def update(self, dt):
        super().update(dt)
        self.move_generated_groups_to_slot_origin()

    def set_cards(self, cards, force=False):
        super().set_cards(cards, force=force)
        self.move_generated_groups_to_slot_origin()

    def get_slot_content_rect(self):
        """Return occupied card bounds in slot frame-local coordinates."""
        return self.slot_content_local_rect.copy()

    def normalize_slot_content(self):
        """Compatibility alias for older callers."""
        self.move_generated_groups_to_slot_origin()

    def move_generated_groups_to_slot_origin(self):
        """Move generated groups so their local bounds start at the slot origin."""
        bounds = self.calculate_generated_groups_local_bounds()
        if bounds is None:
            self.slot_content_local_rect = pygame.Rect(0, 0, 0, 0)
            return

        for group in self.iter_generated_groups():
            rect = group.local_rect
            self.hand_activity.frame.move_group_local(
                group,
                (rect.x - bounds.x, rect.y - bounds.y),
            )

        self.slot_content_local_rect = pygame.Rect(0, 0, bounds.width, bounds.height)

    def calculate_generated_groups_local_bounds(self):
        bounds = None
        for group in self.iter_generated_groups():
            rect = self.get_group_slot_local_rect(group)
            bounds = rect.copy() if bounds is None else bounds.union(rect)
        return bounds

    @staticmethod
    def get_group_slot_local_rect(group):
        return group.local_rect.copy()
