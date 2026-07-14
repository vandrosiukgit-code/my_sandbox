import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from fixtures import action_runner
import screen_layout_config


class ActionRunnerScreenCommandTests(unittest.TestCase):
    def test_screen_command_accepts_table_screen(self):
        parser = action_runner.build_parser()
        args = parser.parse_args(["screen", "table_screen"])
        self.assertEqual(args.command, "screen")
        self.assertEqual(args.screen_id, "table_screen")
        self.assertEqual(args.preset, "opening_hands")

    def test_screen_command_passes_table_screen_preset(self):
        parser = action_runner.build_parser()
        args = parser.parse_args(["screen", "table_screen", "--preset", "take_preview"])
        with mock.patch("fixtures.action_runner.run_table_screen", return_value=0) as run_table_screen:
            result = action_runner.handle_screen(args)

        self.assertEqual(result, 0)
        run_table_screen.assert_called_once_with(preset="take_preview")

    def test_screen_command_rejects_unknown_screen(self):
        parser = action_runner.build_parser()
        args = parser.parse_args(["screen", "missing_screen"])
        result = action_runner.handle_screen(args)
        self.assertEqual(result, 2)

    def test_screen_command_accepts_layout_screen_with_frames(self):
        with TemporaryDirectory() as temp_dir:
            temp_layout_path = Path(temp_dir) / "screen_layout.json"
            with mock.patch.object(screen_layout_config, "SCREEN_LAYOUT_PATH", str(temp_layout_path)):
                payload = screen_layout_config.upsert_screen("test_screen", "test_root_frame", (320, 320))
                screen_layout_config.save_screen_layout(payload)
                parser = action_runner.build_parser()
                args = parser.parse_args(["screen", "test_screen"])
                with mock.patch("fixtures.action_runner.run_layout_screen", return_value=0) as run_layout_screen:
                    result = action_runner.handle_screen(args)

        self.assertEqual(result, 0)
        run_layout_screen.assert_called_once_with("test_screen")

    def test_full_ui_preview_fixture_uses_six_cards_and_filled_table_slots(self):
        fixture = action_runner.build_table_screen_static_fixture("full_ui_preview")

        self.assertEqual(
            fixture["card_counts"],
            {
                "left_player_hand": 6,
                "right_player_hand": 6,
                "top_player_hand": 6,
                "bottom_player_hand": 6,
            },
        )
        self.assertEqual(
            fixture["activities"]["cards_slot_frame"]["cards"],
            ["cards.6_of_clubs", "cards.6_of_diamonds"],
        )
        self.assertEqual(
            fixture["activities"]["cards_slot_frame_7"]["cards"],
            ["cards.q_of_clubs", "cards.q_of_diamonds"],
        )


if __name__ == "__main__":
    unittest.main()
