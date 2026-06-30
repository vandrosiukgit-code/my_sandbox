"""Card conceal/reveal behavior before extracting visibility helpers."""

import unittest

import pygame

from activities.cards_slot_activity import CardsSlotActivityDecorator
from activities.visible_cards_hand_activity import VisibleCardsHandDecorator


class FakeResourceManager:
    @staticmethod
    def get_frames(resource_key):
        surface = pygame.Surface((10, 14), pygame.SRCALPHA)
        if resource_key.endswith("hidden"):
            surface.fill((0, 0, 0, 0))
        else:
            surface.fill((200, 40, 40, 255))
        return [surface]


class FakeFrame:
    def __init__(self):
        self.id = "frame"
        self.local_rect = pygame.Rect(0, 0, 120, 80)
        self.content_rect = self.local_rect.copy()
        self.groups = {}
        self.removed_group_ids = []

    def place_group_local(self, group, position):
        group.set_parent_frame(self)
        group.set_local_position(*position)
        self.groups[group.id] = group

    def set_group_origin(self, group_id, position):
        self.groups[group_id].set_local_position(*position)

    def remove_group(self, group_id):
        self.removed_group_ids.append(group_id)
        self.groups.pop(group_id, None)

    def to_screen(self, position):
        return int(round(position[0])), int(round(position[1]))

    def to_local(self, position):
        return int(round(position[0])), int(round(position[1]))

    def get_content_screen_scale(self):
        return 1.0


class FakeHandActivity:
    def __init__(self):
        self.started = False
        self.provider = None
        self.card_count = 0
        self.base_frames_by_index = {}
        self.sync_calls = 0
        self.layout_calls = 0
        self.clear_calls = 0
        self.generated_groups = []
        self.group_indices = {}

    def configure_card_resources(self, provider=None, layer_name=None, card_count=None):
        self.provider = provider
        self.layer_name = layer_name
        self.card_count = card_count

    def start(self):
        self.started = True
        self.sync_visual_groups()

    def update(self, _dt):
        pass

    def draw(self, _screen):
        pass

    def apply_fixture(self, _fixture):
        pass

    def clear_generated_groups(self):
        self.clear_calls += 1
        self.generated_groups = []
        self.group_indices = {}

    def sync_visual_groups(self):
        self.sync_calls += 1
        while len(self.generated_groups) < self.card_count:
            group = type("Group", (), {"id": f"group-{len(self.generated_groups)}"})()
            self.group_indices[group.id] = len(self.generated_groups)
            self.generated_groups.append(group)

    def apply_fan_layout(self):
        self.layout_calls += 1

    def is_finished(self):
        return False

    def finish(self):
        self.started = False

    def set_card_base_frames(self, hand_index, frames, apply_layout=True):
        self.base_frames_by_index[hand_index] = list(frames)
        if apply_layout:
            self.apply_fan_layout()

    def get_prepared_card_screen_geometry(self, hand_index):
        return {"center": (hand_index, hand_index), "size": (10, 14), "angle_degrees": 0.0}

    def iter_generated_groups(self):
        return tuple(self.generated_groups)

    def get_card_selection_context(self, group):
        return {"hand_index": self.group_indices[group.id], "group_id": group.id}

    def remove_generated_group(self, group, relayout=True):
        if group not in self.generated_groups:
            return None
        self.generated_groups.remove(group)
        self.group_indices = {item.id: index for index, item in enumerate(self.generated_groups)}
        self.card_count = len(self.generated_groups)
        if relayout:
            self.apply_fan_layout()
        return group


class CardVisibilityBehaviorTests(unittest.TestCase):
    def test_visible_hand_prepare_cards_conceals_unrevealed_cards(self):
        hand = FakeHandActivity()
        decorator = VisibleCardsHandDecorator(
            hand,
            resource_manager=FakeResourceManager,
            cards=("cards.6_of_clubs", "cards.7_of_clubs"),
        )

        decorator.prepare_cards(("cards.6_of_clubs", "cards.7_of_clubs"), revealed_count=0)

        self.assertEqual(set(hand.base_frames_by_index), {0, 1})
        for frames in hand.base_frames_by_index.values():
            self.assertEqual(frames[0].get_at((0, 0)).a, 0)

    def test_visible_hand_reveal_restores_resource_frames_once(self):
        hand = FakeHandActivity()
        decorator = VisibleCardsHandDecorator(
            hand,
            resource_manager=FakeResourceManager,
            cards=("cards.6_of_clubs",),
        )
        decorator.prepare_cards(("cards.6_of_clubs",), revealed_count=0)

        self.assertTrue(decorator.reveal_card(0))
        self.assertEqual(hand.base_frames_by_index[0][0].get_at((0, 0)).a, 255)
        self.assertFalse(decorator.reveal_card(0))

    def test_slot_card_visual_state_hides_and_restores_primary_frames(self):
        activity = CardsSlotActivityDecorator(
            FakeFrame(),
            cards=("cards.6_of_clubs",),
            resource_manager=FakeResourceManager,
            max_cards=2,
        )
        activity.start()
        group = activity.get_generated_group(0)

        activity.set_card_visual_state(0, "hidden")
        self.assertEqual(group.get_primary_layer_frames()[0].get_at((0, 0)).a, 0)

        activity.set_card_visual_state(0, "visible")
        self.assertEqual(group.get_primary_layer_frames()[0].get_at((0, 0)).a, 255)

    def test_extract_card_defers_fan_rebuild_until_explicit_rebuild(self):
        activity = FakeHandActivity()
        hand = VisibleCardsHandDecorator(
            activity,
            resource_manager=FakeResourceManager,
            cards=("cards.6_of_clubs", "cards.7_of_clubs", "cards.8_of_clubs"),
        )
        hand.start()
        before_groups = tuple(hand.iter_generated_groups())
        removed_group = before_groups[1]

        self.assertTrue(hand.extract_card_by_group_id(removed_group.id))
        self.assertEqual(len(hand.iter_generated_groups()), 2)
        self.assertEqual(hand.card_resource_keys, ("cards.6_of_clubs", "cards.8_of_clubs"))
        self.assertTrue(hand._pending_layout_rebuild)

        self.assertTrue(hand.rebuild_layout())
        self.assertFalse(hand._pending_layout_rebuild)
        self.assertEqual(len(hand.iter_generated_groups()), 2)
