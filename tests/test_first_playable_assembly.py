import unittest

from core.game_controller import GameController
from core.durak.state import BattlePair, BattleTable, GamePhase
from game_screen.events import ControllerResponse, ScreenInputEvent, VisualCommand
from screens.table_screen import TableScreen


class FakeDeckActivity:
    def __init__(self):
        self.trump_resource_key = None

    def set_trump_resource_key(self, resource_key):
        self.trump_resource_key = resource_key


class FakeDealActivity:
    def __init__(self):
        self.snapshots = []

    def start_deal(self, snapshot):
        self.snapshots.append(snapshot)
        return True


class FirstPlayableAssemblyTests(unittest.TestCase):
    def test_game_controller_start_game_emits_first_visual_commands(self):
        controller = GameController()

        response = controller.start_game()

        self.assertIsInstance(response, ControllerResponse)
        self.assertEqual(
            [command.type for command in response.commands],
            ["deck.set_trump", "deal.initial", "turn.prompt"],
        )
        self.assertEqual(response.state_view["attacker_id"], "bottom_player_hand")
        self.assertEqual(response.state_view["defender_id"], "right_player_hand")

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
        self.assertTrue(response.commands[1].payload["turn_finished"])
        self.assertEqual(response.commands[1].payload["available_card_ids"], ())

    def test_activity_result_after_human_turn_starts_bot_response(self):
        controller = GameController()
        controller.start_game()
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
            type("Result", (), {"payload": {}, "status": "completed"})()
        )

        self.assertEqual(response.commands[0].type, "start_player_turn")
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
            type("Result", (), {"payload": {}, "status": "completed"})()
        )
        self.assertEqual(first_response.commands[0].type, "start_player_turn")
        self.assertEqual(first_response.commands[0].payload["turn_context"]["player_id"], "right_player_hand")

        second_response = controller.handle_activity_result(
            type("Result", (), {"payload": {}, "status": "completed"})()
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
            type("Result", (), {"payload": {}, "status": "completed"})()
        )

        self.assertNotEqual(state.defender_id, "bottom_player_hand")
        self.assertEqual(response.commands[-1].type, "turn.prompt")

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
        self.assertEqual(deal_activity.snapshots, [{"cards_to_deal": {"bottom_player_hand": ("cards.6_of_hearts",)}}])

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


if __name__ == "__main__":
    unittest.main()
