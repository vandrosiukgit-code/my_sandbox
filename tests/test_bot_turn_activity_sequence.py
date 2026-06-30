"""Bot turn sequence behavior before extracting shared action runners."""

import unittest

from activities.bot_turn_activity import BotTurnActivity


class BotTurnActivitySequenceTests(unittest.TestCase):
    def test_build_steps_resets_before_each_bot_by_default(self):
        activity = BotTurnActivity(
            bot_hand_ids=("top_player_hand", "left_player_hand"),
            target_slot_ids=("slot_a", "slot_b"),
            slot_card_positions=("first",),
        )

        self.assertEqual(
            activity.build_steps(),
            [
                {"type": "reset_table_overlay", "bot_hand_id": "top_player_hand"},
                {
                    "type": "move_card",
                    "bot_hand_id": "top_player_hand",
                    "target_slot_id": "slot_a",
                    "slot_card_position": "first",
                },
                {
                    "type": "move_card",
                    "bot_hand_id": "top_player_hand",
                    "target_slot_id": "slot_b",
                    "slot_card_position": "first",
                },
                {"type": "reset_table_overlay", "bot_hand_id": "left_player_hand"},
                {
                    "type": "move_card",
                    "bot_hand_id": "left_player_hand",
                    "target_slot_id": "slot_a",
                    "slot_card_position": "first",
                },
                {
                    "type": "move_card",
                    "bot_hand_id": "left_player_hand",
                    "target_slot_id": "slot_b",
                    "slot_card_position": "first",
                },
            ],
        )

    def test_flight_group_lifecycle_uses_identity_and_clears_on_finish(self):
        first_group = object()
        second_group = object()
        activity = BotTurnActivity()
        activity.flight_groups = [first_group, second_group]

        self.assertEqual(activity.get_next_flight_group_id(), "bot_turn.flight_card.1")
        self.assertEqual(activity.get_next_flight_group_id(), "bot_turn.flight_card.2")

        activity.remove_flight_group(first_group)
        self.assertEqual(activity.iter_generated_groups(), (second_group,))

        activity.finish()
        self.assertEqual(activity.iter_generated_groups(), ())

    def test_land_flight_group_preserves_slot_card_index_for_final_placement(self):
        class PlayAreaSlotsActivity:
            def __init__(self):
                self.calls = []

            def place_player_card(self, card_data):
                self.calls.append(dict(card_data))
                return True

        play_area = PlayAreaSlotsActivity()
        activity = BotTurnActivity(get_activity=lambda activity_id: play_area if activity_id == "play_area_frame" else None)
        removed = []
        activity.remove_flight_group = lambda group: removed.append(group)

        flight_group = object()
        source_group = object()
        activity.land_flight_group(
            flight_group,
            "right_player_hand",
            source_group,
            "cards_slot_frame",
            1,
            "cards.q_of_clubs",
        )

        self.assertEqual(removed, [flight_group])
        self.assertEqual(
            play_area.calls,
            [
                {
                    "resource_key": "cards.q_of_clubs",
                    "target_slot_id": "cards_slot_frame",
                    "slot_card_index": 1,
                }
            ],
        )
        self.assertEqual(activity.pending_source_removals, [("right_player_hand", source_group)])
