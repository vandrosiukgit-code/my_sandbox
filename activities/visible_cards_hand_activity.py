"""Visible-card decorator for player hand fan activities."""

import pygame

from activities.base_activity import Activity


class VisibleCardsHandDecorator(Activity):
    """Decorate a hand fan activity with visible card resources.

    The wrapped activity owns fan geometry and generated groups. This decorator
    owns the player-facing card list and gives the wrapped activity one resource
    key per generated card slot.
    """

    def __init__(
        self,
        hand_activity,
        cards=None,
        resource_manager=None,
        max_cards=None,
        strict_max_cards=False,
        owns_hand_activity=True,
    ):
        super().__init__(duration=0.0)
        self.hand_activity = hand_activity
        self.validate_hand_activity(hand_activity)
        self.resource_manager = resource_manager
        self.max_cards = self.normalize_max_cards(max_cards)
        self.strict_max_cards = bool(strict_max_cards)
        self.owns_hand_activity = bool(owns_hand_activity)
        self.card_resource_keys = self.limit_cards(self.normalize_cards(cards or ()))
        self.revealed_card_indices = set(range(len(self.card_resource_keys)))
        self.configure_hand_activity()

    @staticmethod
    def validate_hand_activity(hand_activity):
        required_methods = (
            "start",
            "update",
            "draw",
            "apply_fixture",
            "clear_generated_groups",
            "sync_visual_groups",
            "apply_fan_layout",
            "is_finished",
            "finish",
            "configure_card_resources",
        )
        for method_name in required_methods:
            if not callable(getattr(hand_activity, method_name, None)):
                raise TypeError(f"hand_activity must provide {method_name}()")

    def configure_hand_activity(self):
        self.hand_activity.configure_card_resources(
            provider=self.get_card_resource_key,
            layer_name="card",
            card_count=len(self.card_resource_keys),
        )

    def start(self):
        if self.started:
            return
        super().start()
        if not getattr(self.hand_activity, "started", False):
            self.hand_activity.start()

    def update(self, dt):
        if not self.started:
            self.start()
        self.hand_activity.update(dt)

    def draw(self, screen):
        self.draw_debug_overlay(screen)

    def draw_debug_overlay(self, screen):
        if hasattr(self.hand_activity, "draw_debug_overlay"):
            self.hand_activity.draw_debug_overlay(screen)
        elif hasattr(self.hand_activity, "draw"):
            self.hand_activity.draw(screen)

    def apply_fixture(self, fixture):
        """Apply visible-card fixture fields and delegate geometry to the hand."""
        if not fixture:
            return

        cards = self.get_fixture_cards(fixture)
        if cards is not None:
            self.set_cards(cards)

        decorated_fixture = dict(fixture)
        decorated_fixture["card_count"] = len(self.card_resource_keys)
        decorated_fixture.pop("resource_key", None)
        self.hand_activity.apply_fixture(decorated_fixture)

    def set_cards(self, cards, force=False):
        """Replace visible cards and force generated groups to use new resources."""
        next_keys = self.limit_cards(self.normalize_cards(cards))
        if not force and next_keys == self.card_resource_keys:
            return

        self.hand_activity.clear_generated_groups()
        self.card_resource_keys = next_keys
        self.revealed_card_indices = set(range(len(self.card_resource_keys)))
        self.configure_hand_activity()
        if getattr(self.hand_activity, "started", False):
            self.hand_activity.sync_visual_groups()
            self.hand_activity.apply_fan_layout()

    def append_cards(self, cards):
        """Append externally dealt visual cards without interpreting game rules."""
        self.set_cards((*self.card_resource_keys, *self.normalize_cards(cards)))

    def prepare_cards(self, cards, revealed_count=0):
        """Build the complete fan once, then conceal panels until they are dealt."""
        self.set_cards(cards, force=True)
        self.revealed_card_indices = set(range(max(0, int(revealed_count))))
        for hand_index, resource_key in enumerate(self.card_resource_keys):
            self.hand_activity.set_card_base_frames(
                hand_index,
                [self.create_transparent_card_surface(resource_key)],
                apply_layout=False,
            )
        self.hand_activity.apply_fan_layout()
        for hand_index in tuple(self.revealed_card_indices):
            self.reveal_card(hand_index)

    def reveal_card(self, hand_index):
        """Reveal one already-positioned card without rebuilding the fan."""
        if hand_index in self.revealed_card_indices:
            return False
        resource_key = self.card_resource_keys[hand_index]
        self.hand_activity.set_card_base_frames(
            hand_index,
            self.resource_manager.get_frames(resource_key),
            apply_layout=True,
        )
        self.revealed_card_indices.add(hand_index)
        return True

    def get_prepared_card_screen_geometry(self, hand_index):
        """Expose one prepared visual slot as an Action target."""
        return self.hand_activity.get_prepared_card_screen_geometry(hand_index)

    def create_transparent_card_surface(self, resource_key):
        frames = self.resource_manager.get_frames(resource_key)
        if not frames:
            raise KeyError(f"Card resource has no frames: {resource_key!r}")
        return pygame.Surface(frames[0].get_size(), pygame.SRCALPHA)

    def remove_card_by_group_id(self, group_id):
        """Remove one visual card while preserving the wrapper card list order."""
        for group in self.hand_activity.iter_generated_groups():
            if group.id != group_id:
                continue
            context = self.hand_activity.get_card_selection_context(group)
            index = context.get("hand_index") if context is not None else None
            if index is None or not 0 <= index < len(self.card_resource_keys):
                return False
            cards = list(self.card_resource_keys)
            cards.pop(index)
            self.set_cards(cards, force=True)
            return True
        return False

    def get_card_resource_key(self, index):
        if index < 0 or index >= len(self.card_resource_keys):
            raise RuntimeError("VisibleCardsHandDecorator card index is out of range")
        return self.card_resource_keys[index]

    def is_finished(self):
        return self._finished or self.hand_activity.is_finished()

    def finish(self):
        if self.owns_hand_activity:
            self.hand_activity.finish()
        super().finish()

    def iter_generated_groups(self):
        """Return generated visual groups owned by the wrapped hand activity."""
        if hasattr(self.hand_activity, "iter_generated_groups"):
            return tuple(self.hand_activity.iter_generated_groups())
        return tuple(getattr(self.hand_activity, "generated_groups", ()))

    def get_layout_signature(self):
        """Return the wrapped hand layout signature when available."""
        getter = getattr(self.hand_activity, "get_layout_signature", None)
        if callable(getter):
            return getter()
        return tuple(
            (
                group.id,
                tuple(group.local_rect),
                1.0 if group.scale_factor is None else group.scale_factor,
            )
            for group in self.iter_generated_groups()
        )

    def get_card_selection_context(self, group):
        """Return controller-facing selection data for a wrapped hand group."""
        if not hasattr(self.hand_activity, "get_card_selection_context"):
            return None
        context = self.hand_activity.get_card_selection_context(group)
        if context is None:
            return None
        hand_index = context.get("hand_index")
        if hand_index is not None and 0 <= hand_index < len(self.card_resource_keys):
            resource_key = self.card_resource_keys[hand_index]
            context = dict(context)
            context["card_id"] = resource_key
            context["resource_key"] = resource_key
        return context

    def get_fixture_cards(self, fixture):
        for key in ("cards", "card_resource_keys", "resource_keys"):
            if key in fixture:
                return fixture[key]
        if fixture.get("cards_from_manifest"):
            return self.get_manifest_card_keys(fixture)
        return None

    def get_manifest_card_keys(self, fixture):
        """Temporary GUI debug source; Controller must provide real hand cards."""
        if self.resource_manager is None:
            raise RuntimeError("cards_from_manifest requires resource_manager")

        resource_keys = tuple(
            key
            for key in sorted(self.resource_manager.get_runtime_cache())
            if key.startswith("cards.") and key != "cards.card_back"
        )
        start, stop = self.get_fixture_slice_bounds(fixture)
        return resource_keys[start:stop]

    @staticmethod
    def normalize_cards(cards):
        normalized = []
        for card in cards or ():
            if isinstance(card, str):
                normalized.append(card)
            elif isinstance(card, dict):
                resource_key = card.get("resource_key") or card.get("key")
                if not resource_key:
                    raise TypeError(f"Card descriptor requires resource_key or key: {card!r}")
                normalized.append(str(resource_key))
            else:
                raise TypeError(f"Unsupported card descriptor: {card!r}")
        return tuple(normalized)

    def limit_cards(self, cards):
        if self.max_cards is None:
            return tuple(cards)
        if self.strict_max_cards and len(cards) > self.max_cards:
            raise ValueError(f"Too many cards: {len(cards)} > {self.max_cards}")
        return tuple(cards)[: self.max_cards]

    @staticmethod
    def normalize_max_cards(max_cards):
        if max_cards is None:
            return None
        value = int(max_cards)
        if value < 0:
            raise ValueError(f"max_cards must be non-negative: {max_cards!r}")
        return value

    @staticmethod
    def normalize_slice(card_slice):
        if isinstance(card_slice, dict):
            start = card_slice.get("start", 0)
            stop = card_slice.get("stop", card_slice.get("end"))
        else:
            if not isinstance(card_slice, (tuple, list)):
                raise TypeError("card_slice must be dict, tuple or list")
            values = tuple(card_slice)
            start = values[0] if len(values) >= 1 else 0
            stop = values[1] if len(values) >= 2 else None
        start = 0 if start is None else int(start)
        stop = None if stop is None else int(stop)
        start = max(0, start)
        if stop is not None:
            stop = max(start, stop)
        return start, stop

    @classmethod
    def get_fixture_slice_bounds(cls, fixture):
        card_slice = fixture.get("card_slice", fixture.get("cards_slice"))
        if card_slice is None:
            start, stop = 0, None
        else:
            start, stop = cls.normalize_slice(card_slice)

        if "card_count" in fixture:
            count = max(0, int(fixture["card_count"]))
            stop = start + count
        return start, stop
