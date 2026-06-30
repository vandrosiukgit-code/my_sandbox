"""Long-lived visual activity for a deck and its face-up trump card."""

import pygame

from activities.base_activity import Activity
from group import Group


class DeckActivity(Activity):
    """Own visual-only deck-back and face-up trump groups in one Frame."""

    EMPTY_DECK_ALPHA = 120
    TAKEN_TRUMP_ALPHA = 120
    EMPTY_DECK_TINT = (90, 90, 90, 255)

    def __init__(
        self,
        frame,
        resource_manager,
        resource_key="cards.card_back",
        trump_resource_key="cards.a_of_spades",
        group_id=None,
        deal_cards_callback=None,
        deck_empty_alpha=None,
        trump_taken_alpha=None,
    ):
        super().__init__(duration=0.0)
        self.frame = frame
        self.resource_manager = resource_manager
        self.resource_key = resource_key
        self.trump_resource_key = trump_resource_key
        self.group_id = group_id or f"{frame.id}.card_back"
        self.trump_group_id = f"{frame.id}.trump"
        self.deal_cards_callback = deal_cards_callback
        self.deck_empty_alpha = self.EMPTY_DECK_ALPHA if deck_empty_alpha is None else int(deck_empty_alpha)
        self.trump_taken_alpha = self.TAKEN_TRUMP_ALPHA if trump_taken_alpha is None else int(trump_taken_alpha)
        self.deck_group = None
        self.trump_group = None
        self.last_deal_requests = ()
        self.deck_count = 1
        self._deck_empty_visual_applied = False
        self._trump_taken_visual_applied = False
        self._deck_group_base_frames = ()
        self._trump_group_base_frames = ()

    def start(self):
        if self.started:
            return
        super().start()
        self.deck_group = Group.create_group(
            self.group_id,
            (("card_back", self.resource_key),),
            resource_manager=self.resource_manager,
        )
        self._deck_group_base_frames = self.deck_group.get_primary_layer_frames()
        self.trump_group = Group.create_group(
            self.trump_group_id,
            (("trump_face", self.trump_resource_key),),
            resource_manager=self.resource_manager,
        )
        self.rotate_trump_face()
        self._trump_group_base_frames = self.trump_group.get_primary_layer_frames()
        self.apply_visual_state()
        self.layout_groups()

    def rotate_trump_face(self):
        frames = self.trump_group.get_primary_layer_frames()
        rotated_frames = [pygame.transform.rotate(frame, 90) for frame in frames]
        self.trump_group.set_primary_layer_frames(rotated_frames)
        width, height = rotated_frames[0].get_size()
        self.trump_group.set_local_rect((0, 0, width, height))
        self.trump_group.set_scale_factor(self.frame.local_rect.width / width)

    def set_trump_resource_key(self, resource_key):
        """Update only the visual trump representation supplied by a caller."""
        resource_key = str(resource_key)
        if resource_key == self.trump_resource_key:
            return
        self.trump_resource_key = resource_key
        if self.trump_group is None:
            return
        self.frame.remove_group(self.trump_group.id)
        self.trump_group = Group.create_group(
            self.trump_group_id,
            (("trump_face", self.trump_resource_key),),
            resource_manager=self.resource_manager,
        )
        self.rotate_trump_face()
        self._trump_group_base_frames = self.trump_group.get_primary_layer_frames()
        self.apply_visual_state()
        self.layout_groups()

    def set_deck_count(self, deck_count):
        """Update only the visual empty/non-empty deck state supplied by a caller."""
        try:
            normalized_count = max(0, int(deck_count))
        except (TypeError, ValueError):
            return
        if normalized_count == self.deck_count and self.deck_group is not None:
            return
        self.deck_count = normalized_count
        self.apply_visual_state()

    def apply_visual_state(self):
        self.apply_deck_visual_state()
        self.apply_trump_visual_state()

    def apply_deck_visual_state(self):
        if self.deck_group is None:
            return
        if not self._deck_group_base_frames:
            self._deck_group_base_frames = self.deck_group.get_primary_layer_frames()
        should_dim = self.deck_count <= 0
        if should_dim == self._deck_empty_visual_applied:
            return
        if should_dim:
            self.deck_group.set_primary_layer_frames(
                tuple(self.build_dimmed_frame(frame, self.deck_empty_alpha) for frame in self._deck_group_base_frames)
            )
        else:
            self.deck_group.set_primary_layer_frames(self._deck_group_base_frames)
        self._deck_empty_visual_applied = should_dim

    def apply_trump_visual_state(self):
        if self.trump_group is None:
            return
        if not self._trump_group_base_frames:
            self._trump_group_base_frames = self.trump_group.get_primary_layer_frames()
        should_dim = self.deck_count <= 0
        if should_dim == self._trump_taken_visual_applied:
            return
        if should_dim:
            self.trump_group.set_primary_layer_frames(
                tuple(self.build_dimmed_frame(frame, self.trump_taken_alpha) for frame in self._trump_group_base_frames)
            )
        else:
            self.trump_group.set_primary_layer_frames(self._trump_group_base_frames)
        self._trump_taken_visual_applied = should_dim

    @classmethod
    def build_dimmed_frame(cls, frame, alpha):
        dimmed = frame.copy()
        dimmed.fill(cls.EMPTY_DECK_TINT, special_flags=pygame.BLEND_RGBA_MULT)
        dimmed.set_alpha(int(alpha))
        return dimmed

    def layout_groups(self):
        """Place both visual deck groups inside the assigned local Frame."""
        trump_rect = self.trump_group.get_scaled_local_rect()
        deck_local_x = (self.frame.local_rect.width - self.deck_group.local_rect.width) // 2
        self.frame.place_group_local(
            self.trump_group,
            (
                deck_local_x + self.deck_group.local_rect.width - trump_rect.width,
                (self.frame.local_rect.height - trump_rect.height) // 2,
            ),
        )
        self.frame.place_group_local(self.deck_group, (deck_local_x, 0))

    def deal_cards(self, deal_requests):
        """Accept controller-shaped visual deals without owning player activities."""
        normalized_requests = self.normalize_deal_requests(deal_requests)
        if normalized_requests == self.last_deal_requests:
            return
        self.last_deal_requests = normalized_requests
        if self.deal_cards_callback is None:
            return
        for target_activity_id, card_resource_keys in self.last_deal_requests:
            self.deal_cards_callback(target_activity_id, card_resource_keys)

    def get_deal_source_screen_geometry(self):
        """Return the visible deck-back geometry for a transient deal Action."""
        if self.deck_group is None:
            return None
        return {"center": self.deck_group.rect.center, "size": self.deck_group.rect.size}

    @staticmethod
    def normalize_deal_requests(deal_requests):
        if deal_requests is None:
            return ()
        if not isinstance(deal_requests, (list, tuple)):
            raise TypeError("deals must be a list of deal descriptors")

        normalized = []
        for request in deal_requests:
            if not isinstance(request, dict):
                raise TypeError("each deal must be a dictionary")
            target_activity_id = request.get("target_activity_id")
            card_resource_keys = request.get("card_resource_keys", request.get("cards"))
            if not isinstance(target_activity_id, str) or not target_activity_id:
                raise ValueError("deal requires target_activity_id")
            if not isinstance(card_resource_keys, (list, tuple)) or not all(
                isinstance(resource_key, str) and resource_key for resource_key in card_resource_keys
            ):
                raise ValueError("deal requires card_resource_keys as non-empty strings")
            normalized.append((target_activity_id, tuple(card_resource_keys)))
        return tuple(normalized)

    def update(self, dt):
        _ = dt
        if not self.started:
            self.start()

    def apply_fixture(self, fixture):
        """Accept a controller-shaped deck snapshot from development fixtures.

        Supported fields are ``trump_resource_key``, ``deck_count``,
        ``deck_empty_alpha``, ``trump_taken_alpha`` and ``deals``. A deal has
        ``target_activity_id`` and ``card_resource_keys``.  The callback is
        injected by the screen, so this Activity never resolves or mutates a
        player hand itself.
        """
        if not fixture:
            return
        if "trump_resource_key" in fixture:
            self.set_trump_resource_key(fixture["trump_resource_key"])
        if "deck_empty_alpha" in fixture:
            self.deck_empty_alpha = int(fixture["deck_empty_alpha"])
        if "trump_taken_alpha" in fixture:
            self.trump_taken_alpha = int(fixture["trump_taken_alpha"])
        if "deck_count" in fixture:
            self.set_deck_count(fixture["deck_count"])
        if "deals" in fixture:
            self.deal_cards(fixture["deals"])

    def iter_generated_groups(self):
        return tuple(group for group in (self.trump_group, self.deck_group) if group is not None)

    def finish(self):
        for group in (self.trump_group, self.deck_group):
            if group is not None:
                self.frame.remove_group(group.id)
        self.trump_group = None
        self.deck_group = None
        self._deck_group_base_frames = ()
        self._trump_group_base_frames = ()
        super().finish()
