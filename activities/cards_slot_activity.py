"""Cards slot decorator activity for the central play area."""

import pygame

from activities.visible_cards_hand_activity import VisibleCardsHandDecorator


class CardsSlotActivityDecorator(VisibleCardsHandDecorator):
    """Temporary table slot decorator; Controller will provide real table cards."""

    def __init__(self, hand_activity, cards=None, resource_manager=None):
        super().__init__(
            hand_activity,
            cards=cards,
            resource_manager=resource_manager,
            max_cards=2,
        )
        self.slot_content_rect = pygame.Rect(0, 0, 0, 0)

    def apply_fixture(self, fixture):
        super().apply_fixture(fixture)
        self.normalize_slot_content()

    def get_slot_content_rect(self):
        """Return the slot content bounds available to external layout modules."""
        return self.slot_content_rect.copy()

    def normalize_slot_content(self):
        bounds = self.calculate_generated_groups_bounds()
        if bounds is None:
            self.slot_content_rect = pygame.Rect(0, 0, 0, 0)
            return

        for group in self.hand_activity.generated_groups:
            rect = group.local_rect
            group.set_local_position(rect.x - bounds.x, rect.y - bounds.y)
            self.hand_activity.frame.group_origins[group.id] = group.local_rect.topleft

        self.slot_content_rect = pygame.Rect(0, 0, bounds.width, bounds.height)

    def calculate_generated_groups_bounds(self):
        bounds = None
        for group in self.hand_activity.generated_groups:
            rect = self.get_group_slot_rect(group)
            bounds = rect.copy() if bounds is None else bounds.union(rect)
        return bounds

    @staticmethod
    def get_group_slot_rect(group):
        if hasattr(group, "get_scaled_local_rect"):
            return group.get_scaled_local_rect()
        return group.local_rect
