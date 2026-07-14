import unittest
import random

from core.game_controller import GameController
from core.durak.state import BattlePair, BattleTable, GamePhase
from game_screen.events import ControllerResponse, ScreenInputEvent, VisualCommand
from screens.table_screen import TableScreen


class FakeDeckActivity:
    def __init__(self):
        self.trump_resource_key = None
        self.deck_count = None

    def set_trump_resource_key(self, resource_key):
        self.trump_resource_key = resource_key

    def set_deck_count(self, deck_count):
        self.deck_count = deck_count


class FakeDealActivity:
    def __init__(self):
        self.snapshots = []

    def start_deal(self, snapshot):
        self.snapshots.append(snapshot)
        return True


class FakeHandActivity:
    def __init__(self, remove_result=True):
        self.remove_result = remove_result
        self.removed_group_ids = []
        self.extracted_group_ids = []
        self.rebuild_calls = 0
        self.pending_layout_rebuild = False

    def remove_card_by_group_id(self, group_id):
        self.removed_group_ids.append(group_id)
        return self.remove_result

    def extract_card_by_group_id(self, group_id):
        self.extracted_group_ids.append(group_id)
        return self.remove_result

    def rebuild_layout(self):
        self.rebuild_calls += 1
        self.pending_layout_rebuild = False
        return True

    def has_pending_layout_rebuild(self):
        return self.pending_layout_rebuild


class FirstPlayableAssemblyTests(unittest.TestCase):
    def test_create_shuffled_deck_varies_trump_candidate_across_seeds(self):
        trump_candidates = {
            GameController.create_shuffled_deck(random.Random(seed))[24].card_id
            for seed in range(12)
        }

        self.assertGreater(len(trump_candidates), 1)
        self.assertEqual(len(GameController.create_shuffled_deck(random.Random(7))), 36)

    def test_game_controller_start_game_emits_first_visual_commands(self):
        controller = GameController()

        response = controller.start_game()

        self.assertIsInstance(response, ControllerResponse)
        self.assertEqual(
            [command.type for command in response.commands],
            ["deck.set_trump", "deal.initial"],
        )
        self.assertEqual(response.state_view["attacker_id"], "bottom_player_hand")
        self.assertEqual(response.state_view["defender_id"], "right_player_hand")

    def test_game_controller_provides_end_game_stats(self):
        controller = GameController()
        controller.start_game()
        controller.record_moves_from_events(
            (
                type("Event", (), {"type": "cards_attacked"})(),
                type("Event", (), {"type": "card_defended"})(),
            )
        )
        controller.durak_game.state.fool_id = "right_player_hand"
        controller.durak_game.state.phase = GamePhase.FINISHED

        stats = controller.get_end_game_stats()

        self.assertEqual(stats["moves_count"], 2)
        self.assertEqual(stats["loser"], "Right Bot")
        self.assertEqual(stats["loser_id"], "right_player_hand")
        self.assertIn("Player", stats["winner"])
        self.assertEqual(stats["phase"], "finished")

    def test_initial_deal_command_contains_real_bottom_cards_and_hidden_bot_cards(self):
        controller = GameController()

        deal_command = controller.start_game().commands[1]
        cards_to_deal = deal_command.payload["cards_to_deal"]

        self.assertEqual(len(cards_to_deal["bottom_player_hand"]), 6)
        self.assertIn("cards.6_of_hearts", cards_to_deal["bottom_player_hand"])
        self.assertEqual(cards_to_deal["right_player_hand"], ("cards.card_back",) * 6)
        self.assertEqual(cards_to_deal["top_player_hand"], ("cards.card_back",) * 6)
        self.assertEqual(cards_to_deal["left_player_hand"], ("cards.card_back",) * 6)

    def test_human_card_click_applies_domain_attack_and_emits_play_command(self):
        controller = GameController()
        controller.start_game()
        controller.handle_activity_result(
            type("Result", (), {"payload": {}, "status": "completed", "type": "deal.completed"})()
        )
        input_event = ScreenInputEvent(
            type="click",
            payload={
                "selected_card": {
                    "group_id": "bottom-group-0",
                    "card_id": "cards.6_of_hearts",
                    "resource_key": "cards.6_of_hearts",
                    "source_screen_geometry": {"center": (10, 10), "size": (20, 30)},
                }
            },
        )

        response = controller.handle_input(input_event)

        self.assertEqual(response.commands[0].type, "start_player_turn")
        self.assertEqual(
            response.commands[0].payload["turn_context"]["card_id"],
            "cards.6_of_hearts",
        )
        self.assertEqual(controller.durak_game.state.table.pairs[0].attack_card_id, "cards.6_of_hearts")
        self.assertEqual(len(response.commands), 1)

    def test_activity_result_after_human_turn_starts_bot_response(self):
        controller = GameController()
        controller.start_game()
        controller.handle_activity_result(
            type("Result", (), {"payload": {}, "status": "completed", "type": "deal.completed"})()
        )
        controller.handle_input(
            ScreenInputEvent(
                type="click",
                payload={
                    "selected_card": {
                        "group_id": "bottom-group-0",
                        "player_id": "bottom_player_hand",
                        "card_id": "cards.6_of_hearts",
                        "resource_key": "cards.6_of_hearts",
                        "source_screen_geometry": {"center": (10, 10), "size": (20, 30)},
                    }
                },
            )
        )

        response = controller.handle_activity_result(
            type("Result", (), {"payload": {}, "status": "completed", "type": "turn.completed"})()
        )

        self.assertIn(response.commands[0].type, {"start_player_turn", "table.take"})
        if response.commands[0].type == "start_player_turn":
            self.assertNotEqual(
                response.commands[0].payload["turn_context"]["player_id"],
                "bottom_player_hand",
            )

    def test_bot_defense_keeps_throw_in_window_open_for_human(self):
        controller = GameController()
        controller.start_game()
        state = controller.durak_game.state
        state.phase = GamePhase.DEFENDING
        state.attacker_id = "bottom_player_hand"
        state.defender_id = "right_player_hand"
        state.get_participant("bottom_player_hand").hand[:] = ["cards.6_of_spades"]
        state.get_participant("right_player_hand").hand[:] = ["cards.7_of_clubs"]
        state.table = BattleTable(
            pairs=[BattlePair("cards.6_of_clubs")],
            defender_initial_hand_size=6,
        )

        first_response = controller.handle_activity_result(
            type("Result", (), {"payload": {}, "status": "completed", "type": "turn.completed"})()
        )
        self.assertEqual(first_response.commands[0].type, "start_player_turn")
        self.assertEqual(first_response.commands[0].payload["turn_context"]["player_id"], "right_player_hand")

        second_response = controller.handle_activity_result(
            type("Result", (), {"payload": {}, "status": "completed", "type": "turn.completed"})()
        )

        self.assertEqual(controller.durak_game.state.phase, GamePhase.DEFENDING)
        self.assertEqual(controller.durak_game.state.table.pairs[0].defense_card_id, "cards.7_of_clubs")
        self.assertEqual([command.type for command in second_response.commands], ["turn.prompt"])
        self.assertEqual(second_response.commands[0].payload["available_card_ids"], ("cards.6_of_spades",))

    def test_activity_result_can_force_human_take_when_no_defense_options_exist(self):
        controller = GameController()
        controller.start_game()
        state = controller.durak_game.state
        state.phase = GamePhase.DEFENDING
        state.attacker_id = "right_player_hand"
        state.defender_id = "bottom_player_hand"
        state.get_participant("bottom_player_hand").hand[:] = ["cards.6_of_clubs"]
        state.table.pairs = [BattlePair("cards.a_of_hearts")]

        response = controller.handle_activity_result(
            type("Result", (), {"payload": {}, "status": "completed", "type": "turn.completed"})()
        )

        self.assertEqual(state.defender_id, "bottom_player_hand")
        self.assertEqual(response.commands[-1].type, "turn.prompt")
        self.assertTrue(response.commands[-1].payload["can_take_cards"])

    def test_cards_taken_from_empty_deck_do_not_queue_fake_follow_up_deal(self):
        controller = GameController()
        controller.start_game()
        state = controller.durak_game.state
        state.deck.card_ids[:] = []
        previous_snapshot = controller.durak_game.build_snapshot()
        current_state = controller.durak_game.state
        current_state.get_participant("bottom_player_hand").hand[:] = ["cards.6_of_clubs", "cards.a_of_hearts"]
        domain_result = controller.durak_game.build_result(
            events=(
                type(
                    "Event",
                    (),
                    {"type": "cards_taken", "payload": {"player_id": "bottom_player_hand", "card_ids": ["cards.a_of_hearts"]}},
                )(),
            ),
            waiting_player_ids=(),
        )

        commands = controller.build_commands_from_domain_result(domain_result, previous_snapshot)

        self.assertEqual([command.type for command in commands], ["table.take"])
        self.assertEqual(controller.flush_pending_visual_commands(), ())

    def test_turn_prompt_keeps_human_turn_open_when_throw_in_cards_remain(self):
        controller = GameController()
        controller.start_game()
        state = controller.durak_game.state
        state.phase = GamePhase.DEFENDING
        state.attacker_id = "bottom_player_hand"
        state.defender_id = "right_player_hand"
        state.get_participant("bottom_player_hand").hand[:] = ["cards.6_of_spades"]
        state.table = BattleTable(
            pairs=[BattlePair("cards.6_of_hearts", "cards.7_of_hearts")],
            defender_initial_hand_size=6,
        )
        response = controller.build_turn_prompt_command()

        self.assertFalse(response.payload["turn_finished"])
        self.assertEqual(response.payload["available_card_ids"], ("cards.6_of_spades",))

    def test_turn_prompt_offers_only_defense_cards_that_can_beat_attack(self):
        controller = GameController()
        controller.start_game()
        state = controller.durak_game.state
        state.phase = GamePhase.DEFENDING
        state.attacker_id = "right_player_hand"
        state.defender_id = "bottom_player_hand"
        bottom_player = state.get_participant("bottom_player_hand")
        bottom_player.hand[:] = ["cards.7_of_hearts", "cards.8_of_clubs", "cards.9_of_hearts"]
        state.table.pairs = [BattlePair("cards.8_of_hearts")]

        prompt = controller.build_turn_prompt_command()

        self.assertEqual(
            prompt.payload["available_card_ids"],
            ("cards.9_of_hearts",),
        )
        self.assertFalse(prompt.payload["turn_finished"])

    def test_table_screen_dispatches_deck_and_initial_deal_commands(self):
        screen = object.__new__(TableScreen)
        deck_activity = FakeDeckActivity()
        deal_activity = FakeDealActivity()
        activities = {
            "deck_frame": deck_activity,
            "card_deal_sequence": deal_activity,
        }
        screen.get_named_activity = activities.get

        screen.dispatch_visual_command(
            VisualCommand(
                type="deck.set_trump",
                payload={"resource_key": "cards.a_of_hearts"},
            )
        )
        screen.dispatch_visual_command(
            VisualCommand(
                type="deal.initial",
                payload={"cards_to_deal": {"bottom_player_hand": ("cards.6_of_hearts",)}},
            )
        )

        self.assertEqual(deck_activity.trump_resource_key, "cards.a_of_hearts")
        self.assertIsNone(deck_activity.deck_count)
        self.assertEqual(deal_activity.snapshots, [{"cards_to_deal": {"bottom_player_hand": ("cards.6_of_hearts",)}}])

    def test_table_screen_dispatches_deck_count_to_deck_activity(self):
        screen = object.__new__(TableScreen)
        deck_activity = FakeDeckActivity()
        screen.get_named_activity = lambda activity_id: deck_activity if activity_id == "deck_frame" else None

        screen.dispatch_visual_command(
            VisualCommand(
                type="deck.set_trump",
                payload={"resource_key": "cards.a_of_hearts", "deck_count": 0},
            )
        )

        self.assertEqual(deck_activity.trump_resource_key, "cards.a_of_hearts")
        self.assertEqual(deck_activity.deck_count, 0)

    def test_table_screen_syncs_deck_count_from_controller_state_view(self):
        screen = object.__new__(TableScreen)
        deck_activity = FakeDeckActivity()
        screen.get_named_activity = lambda activity_id: deck_activity if activity_id == "deck_frame" else None

        commands = screen.get_controller_response_commands(
            ControllerResponse(
                commands=(VisualCommand(type="turn.prompt"),),
                state_view={"deck_count": 0},
            )
        )

        self.assertEqual([command.type for command in commands], ["turn.prompt"])
        self.assertEqual(deck_activity.deck_count, 0)

    def test_deal_completion_opens_human_prompt_after_start_animation(self):
        controller = GameController()

        controller.start_game()
        response = controller.handle_activity_result(
            type("Result", (), {"payload": {}, "status": "completed", "type": "deal.completed"})()
        )

        self.assertEqual([command.type for command in response.commands], ["turn.prompt"])
        self.assertEqual(response.commands[0].payload["available_card_ids"][0], "cards.6_of_hearts")

    def test_table_screen_start_dispatches_controller_start_commands_once(self):
        screen = object.__new__(TableScreen)
        calls = []

        class Controller:
            def __init__(self):
                self.starts = 0

            def start_game(self):
                self.starts += 1
                return ControllerResponse(commands=(VisualCommand(type="turn.prompt"),))

        controller = Controller()
        screen.game_controller = controller
        screen.controller_game_started = False
        screen.controller_owned_visual_state = False
        screen.dispatch_visual_commands = lambda commands: calls.extend(commands)

        screen.start_controller_game()
        screen.start_controller_game()

        self.assertEqual(controller.starts, 1)
        self.assertEqual([command.type for command in calls], ["turn.prompt"])
        self.assertTrue(screen.controller_owned_visual_state)

    def test_table_screen_resolves_bot_turn_context_from_hand_activity(self):
        class HandActivity:
            def iter_generated_groups(self):
                return (type("Group", (), {"id": "right-group-0"})(),)

            def get_card_selection_context(self, group):
                return {
                    "group_id": group.id,
                    "player_id": "right_player_hand",
                    "card_id": "cards.7_of_hearts",
                    "resource_key": "cards.7_of_hearts",
                }

            def get_group_card_screen_geometry(self, _group):
                return {"center": (100, 100), "size": (20, 30), "angle_degrees": 0.0}

        screen = object.__new__(TableScreen)
        activities = {"right_player_hand": HandActivity()}
        screen.get_named_activity = activities.get

        context = screen.resolve_turn_context(
            {
                "player_id": "right_player_hand",
                "card_id": "cards.7_of_hearts",
                "resource_key": "cards.7_of_hearts",
            }
        )

        self.assertEqual(context["group_id"], "right-group-0")
        self.assertEqual(context["source_screen_geometry"]["center"], (100, 100))

    def test_turn_completion_forwards_command_id_to_controller(self):
        class TurnActivity:
            def consume_completed_turn_context(self):
                return {"command_id": "cmd-play", "card_id": "cards.6_of_hearts"}

        screen = object.__new__(TableScreen)
        screen.get_named_activity = lambda activity_id: TurnActivity() if activity_id == "play_area_frame" else None
        forwarded = []
        screen.forward_activity_result_to_controller = lambda result: forwarded.append(result) or ()
        screen.dispatch_visual_commands = lambda commands: None

        screen.forward_completed_turn_results()

        self.assertEqual(len(forwarded), 1)
        self.assertEqual(forwarded[0].command_id, "cmd-play")

    def test_remove_bottom_player_hand_card_freezes_bottom_layout(self):
        screen = object.__new__(TableScreen)
        hand_activity = FakeHandActivity(remove_result=True)
        screen.get_named_activity = lambda activity_id: hand_activity if activity_id == "bottom_player_hand" else None
        screen._bottom_player_hand_layout_lock_depth = 0
        screen._bottom_player_hand_turn_rebuild_pending = False

        removed = screen.remove_hand_card(
            {
                "group_id": "bottom-group-0",
                "player_id": "bottom_player_hand",
            }
        )

        self.assertTrue(removed)
        self.assertEqual(screen._bottom_player_hand_layout_lock_depth, 1)
        self.assertTrue(screen._bottom_player_hand_turn_rebuild_pending)
        self.assertEqual(hand_activity.extracted_group_ids, ["bottom-group-0"])
        self.assertEqual(hand_activity.removed_group_ids, [])

    def test_non_bottom_hand_card_removal_does_not_freeze_bottom_layout(self):
        screen = object.__new__(TableScreen)
        hand_activity = FakeHandActivity(remove_result=True)
        screen.get_named_activity = lambda activity_id: hand_activity if activity_id == "right_player_hand" else None
        screen._bottom_player_hand_layout_lock_depth = 0
        screen._bottom_player_hand_turn_rebuild_pending = False

        removed = screen.remove_hand_card(
            {
                "group_id": "right-group-0",
                "player_id": "right_player_hand",
            }
        )

        self.assertTrue(removed)
        self.assertEqual(screen._bottom_player_hand_layout_lock_depth, 0)
        self.assertFalse(screen._bottom_player_hand_turn_rebuild_pending)
        self.assertEqual(hand_activity.removed_group_ids, ["right-group-0"])

    def test_turn_completion_rebuilds_bottom_hand_before_forwarding_result(self):
        class TurnActivity:
            def consume_completed_turn_context(self):
                return {"command_id": "cmd-play", "card_id": "cards.6_of_hearts"}

        hand_activity = FakeHandActivity(remove_result=True)
        screen = object.__new__(TableScreen)
        screen.get_named_activity = (
            lambda activity_id: TurnActivity()
            if activity_id == "play_area_frame"
            else hand_activity
            if activity_id == "bottom_player_hand"
            else None
        )
        order = []
        screen.forward_activity_result_to_controller = lambda result: order.append(("forward", result.type)) or ()
        screen.dispatch_visual_commands = lambda commands: None
        screen._bottom_player_hand_turn_rebuild_pending = True
        original_rebuild = screen.rebuild_bottom_player_hand_after_turn

        def wrapped_rebuild():
            order.append(("rebuild", "bottom_player_hand"))
            return original_rebuild()

        screen.rebuild_bottom_player_hand_after_turn = wrapped_rebuild

        screen.forward_completed_turn_results()

        self.assertEqual(order[0], ("rebuild", "bottom_player_hand"))
        self.assertEqual(order[1], ("forward", "turn.completed"))
        self.assertEqual(hand_activity.rebuild_calls, 1)
        self.assertFalse(screen._bottom_player_hand_turn_rebuild_pending)

    def test_update_rebuilds_bottom_hand_when_turn_visuals_are_already_settled(self):
        hand_activity = FakeHandActivity(remove_result=True)
        hand_activity.pending_layout_rebuild = True

        class TurnActivity:
            turn_active = False
            current_action = None
            slot_layout_release_pending = False

            def consume_completed_turn_context(self):
                return None

        screen = object.__new__(TableScreen)
        screen._fixture_check_elapsed = 0.0
        screen._fixture_check_interval = 999.0
        screen.reload_fixture_if_changed = lambda: None
        screen.configure_bottom_player_hand_fan_area = lambda: None
        screen.forward_activity_completion_results = lambda: None
        screen.forward_completed_turn_results = lambda: None
        screen.release_pending_bottom_player_hand_layout = lambda: None
        screen._bottom_player_hand_turn_rebuild_pending = True
        screen.get_named_activity = (
            lambda activity_id: hand_activity
            if activity_id == "bottom_player_hand"
            else TurnActivity()
            if activity_id == "play_area_frame"
            else None
        )
        from game_screen.game_screen import GameScreen
        original_update = GameScreen.update
        GameScreen.update = lambda self, dt: None
        self.addCleanup(setattr, GameScreen, "update", original_update)

        screen.update(0.0)

        self.assertEqual(hand_activity.rebuild_calls, 1)

    def test_bottom_hand_safe_point_rebuilds_bottom_fan_immediately(self):
        hand_activity = FakeHandActivity(remove_result=True)
        hand_activity.pending_layout_rebuild = True
        screen = object.__new__(TableScreen)
        screen.get_named_activity = lambda activity_id: hand_activity if activity_id == "bottom_player_hand" else None
        screen._bottom_player_hand_turn_rebuild_pending = False

        self.assertTrue(
            screen.handle_bottom_player_hand_safe_point(
                "deal.step.safe_point",
                {"player_id": "bottom_player_hand", "hand_index": 3},
            )
        )

        self.assertEqual(hand_activity.rebuild_calls, 1)

    def test_prepare_card_deal_hands_prefers_incremental_hand_contract(self):
        calls = []

        class BottomHand:
            def prepare_incremental_cards(self, before, incoming):
                calls.append(("incremental", tuple(before), tuple(incoming)))

        class BotHand:
            def prepare_incremental_cards(self, before, incoming):
                calls.append(("incremental", tuple(before), tuple(incoming)))

        screen = object.__new__(TableScreen)
        screen.get_named_activity = (
            lambda activity_id: BottomHand()
            if activity_id == "bottom_player_hand"
            else BotHand()
            if activity_id == "right_player_hand"
            else None
        )
        screen.find_nested_activity_with_method = TableScreen.find_nested_activity_with_method

        screen.prepare_card_deal_hands(
            {"bottom_player_hand": ("cards.6_of_clubs",), "right_player_hand": ("cards.card_back",)},
            {"bottom_player_hand": ("cards.7_of_clubs",), "right_player_hand": ("cards.card_back",)},
        )

        self.assertIn(
            ("incremental", ("cards.6_of_clubs",), ("cards.7_of_clubs",)),
            calls,
        )
        self.assertIn(
            ("incremental", ("cards.card_back",), ("cards.card_back",)),
            calls,
        )

    def test_reveal_card_deal_appends_incremental_hand_card_immediately(self):
        calls = []

        class BottomHand:
            def append_revealed_card(self, resource_key):
                calls.append(("append", resource_key))
                return True

        screen = object.__new__(TableScreen)
        screen.get_named_activity = lambda activity_id: BottomHand() if activity_id == "bottom_player_hand" else None
        screen.find_nested_activity_with_method = TableScreen.find_nested_activity_with_method

        screen.reveal_card_deal("bottom_player_hand", "cards.7_of_clubs", 1)

        self.assertEqual(calls, [("append", "cards.7_of_clubs")])

    def test_round_completion_requests_bottom_layout_release(self):
        screen = object.__new__(TableScreen)
        screen._activity_result_watchers = []
        screen._bottom_player_hand_layout_lock_depth = 1
        screen._bottom_player_hand_layout_release_pending = False
        forwarded = []
        screen.forward_activity_result_to_controller = lambda result: forwarded.append(result.type) or ()
        screen.dispatch_visual_commands = lambda commands: None
        watched_activity = type("Activity", (), {"is_finished": lambda self: True})()

        screen.register_activity_result_watcher(
            watched_activity,
            type("Result", (), {"type": "table.discard.completed"})(),
        )

        screen.forward_activity_completion_results()

        self.assertEqual(forwarded, ["table.discard.completed"])
        self.assertTrue(screen._bottom_player_hand_layout_release_pending)

    def test_bottom_layout_release_waits_until_visuals_finish(self):
        screen = object.__new__(TableScreen)
        calls = []
        screen._bottom_player_hand_layout_lock_depth = 1
        screen._bottom_player_hand_layout_release_pending = True
        screen._bottom_player_hand_fan_area_signature = ("locked",)
        screen.has_blocking_visual_activity = lambda: True
        screen.configure_bottom_player_hand_fan_area = lambda: calls.append("configured")

        self.assertFalse(screen.release_pending_bottom_player_hand_layout())
        self.assertEqual(screen._bottom_player_hand_layout_lock_depth, 1)
        self.assertEqual(calls, [])

        screen.has_blocking_visual_activity = lambda: False

        self.assertTrue(screen.release_pending_bottom_player_hand_layout())
        self.assertEqual(screen._bottom_player_hand_layout_lock_depth, 0)
        self.assertFalse(screen._bottom_player_hand_layout_release_pending)
        self.assertIsNone(screen._bottom_player_hand_fan_area_signature)
        self.assertEqual(calls, ["configured"])


if __name__ == "__main__":
    unittest.main()
