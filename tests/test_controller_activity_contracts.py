import unittest

from game_screen.events import ActivityResult, ControllerResponse, ScreenInputEvent, VisualCommand
from game_screen.game_screen import GameScreen


class ControllerActivityContractTests(unittest.TestCase):
    def test_controller_response_normalizes_command_lists_to_tuple(self):
        command = VisualCommand(type="hand.sync", target="player.bottom.hand")

        response = ControllerResponse(commands=[command])

        self.assertEqual(response.commands, (command,))

    def test_controller_response_rejects_non_visual_commands(self):
        with self.assertRaises(TypeError):
            ControllerResponse(commands=[{"type": "hand.sync"}])

    def test_controller_response_preserves_optional_state_view(self):
        state_view = {"phase": "attacking"}

        response = ControllerResponse(state_view=state_view)

        self.assertIs(response.state_view, state_view)

    def test_visual_command_carries_correlation_and_blocking_policy(self):
        command = VisualCommand(
            type="card.play.to_table",
            target="table.attack_0",
            payload={"card_id": "card_6_clubs"},
            command_id="cmd-1",
            blocking=True,
        )

        self.assertEqual(command.command_id, "cmd-1")
        self.assertTrue(command.blocking)
        self.assertEqual(command.payload["card_id"], "card_6_clubs")

    def test_visual_command_rejects_empty_type_and_non_dict_payload(self):
        with self.assertRaises(ValueError):
            VisualCommand(type="")

        with self.assertRaises(TypeError):
            VisualCommand(type="hand.sync", payload=(("card_id", "card_6_clubs"),))

    def test_activity_result_is_screen_to_controller_completion_fact(self):
        result = ActivityResult(
            type="card_selection.completed",
            source="bottom_player_hand",
            command_id="cmd-select",
            payload={"player_id": "human", "card_ids": ["card_6_clubs"]},
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.source, "bottom_player_hand")
        self.assertEqual(result.payload["card_ids"], ["card_6_clubs"])

    def test_activity_result_accepts_cancelled_and_failed_statuses(self):
        cancelled = ActivityResult(type="animation.completed", source="play_area", status="cancelled")
        failed = ActivityResult(type="animation.completed", source="play_area", status="failed")

        self.assertEqual(cancelled.status, "cancelled")
        self.assertEqual(failed.status, "failed")

    def test_activity_result_rejects_invalid_identity_payload_and_status(self):
        with self.assertRaises(ValueError):
            ActivityResult(type="", source="play_area")

        with self.assertRaises(ValueError):
            ActivityResult(type="animation.completed", source="")

        with self.assertRaises(TypeError):
            ActivityResult(type="animation.completed", source="play_area", payload=())

        with self.assertRaises(ValueError):
            ActivityResult(type="animation.completed", source="play_area", status="unknown")

    def test_screen_accepts_controller_response_from_input_handler(self):
        command = VisualCommand(type="turn.prompt", target="player.bottom")

        class Controller:
            def handle_input(self, input_event):
                self.last_input = input_event
                return ControllerResponse(commands=(command,))

        controller = Controller()
        screen = GameScreen(game_controller=controller)
        input_event = ScreenInputEvent(type="click", group_id="card_6_clubs")

        commands = screen.forward_input_to_controller(input_event)

        self.assertEqual(commands, (command,))
        self.assertIs(controller.last_input, input_event)

    def test_screen_preserves_legacy_visual_command_iterable_response(self):
        command = VisualCommand(type="activate_group", group_id="deck")

        class Controller:
            def handle_input(self, _input_event):
                return [command]

        screen = GameScreen(game_controller=Controller())

        self.assertEqual(
            screen.forward_input_to_controller(ScreenInputEvent(type="click")),
            (command,),
        )

    def test_screen_accepts_single_visual_command_response(self):
        command = VisualCommand(type="turn.prompt", target="player.bottom")

        class Controller:
            def handle_input(self, _input_event):
                return command

        screen = GameScreen(game_controller=Controller())

        self.assertEqual(
            screen.forward_input_to_controller(ScreenInputEvent(type="click")),
            (command,),
        )

    def test_screen_forwards_activity_result_to_controller(self):
        command = VisualCommand(type="hand.select.enable", target="player.bottom.hand")
        result = ActivityResult(
            type="animation.completed",
            source="play_area_frame",
            command_id="cmd-play",
            payload={"card_id": "card_6_clubs"},
        )

        class Controller:
            def handle_activity_result(self, activity_result):
                self.last_result = activity_result
                return ControllerResponse(commands=(command,))

        controller = Controller()
        screen = GameScreen(game_controller=controller)

        commands = screen.forward_activity_result_to_controller(result)

        self.assertEqual(commands, (command,))
        self.assertIs(controller.last_result, result)

    def test_screen_rejects_non_activity_result_for_controller_result_path(self):
        screen = GameScreen(game_controller=object())

        with self.assertRaises(TypeError):
            screen.forward_activity_result_to_controller({"type": "animation.completed"})

    def test_missing_activity_result_handler_is_noop(self):
        screen = GameScreen(game_controller=object())
        result = ActivityResult(type="animation.completed", source="play_area_frame")

        self.assertEqual(screen.forward_activity_result_to_controller(result), ())


if __name__ == "__main__":
    unittest.main()
