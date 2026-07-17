import unittest
from unittest import mock

from screens.table_screen import TableScreen


class TableScreenLayoutTests(unittest.TestCase):
    def test_place_configured_groups_from_layout_uses_screen_layout_source(self):
        screen = TableScreen.__new__(TableScreen)
        screen.put_configured_group = mock.Mock()
        screen.has_screen_frame = mock.Mock(side_effect=lambda frame_id: frame_id in {"game_table", "bottom_player_portrait", "play_area_frame"})
        screen.get_configured_group_placements = mock.Mock(
            return_value={
                "table_group": {"frame_id": "game_table", "position": [0, 0]},
                "btn_take": {"frame_id": "bottom_player_portrait", "position": [12, 34]},
                "btn_pass": {"frame_id": "play_area_frame", "position": [56, 78]},
                "orphan_group": {"frame_id": "missing_frame", "position": [1, 2]},
            }
        )

        screen.place_configured_groups_from_layout()

        self.assertEqual(
            screen.put_configured_group.call_args_list,
            [
                mock.call("table_group", "game_table", position=(0, 0)),
                mock.call("btn_take", "bottom_player_portrait", position=(12, 34)),
                mock.call("btn_pass", "play_area_frame", position=(56, 78)),
            ],
        )

    def test_iter_midground_group_ids_returns_active_groups_except_table_and_foreground(self):
        screen = TableScreen.__new__(TableScreen)
        screen.active_group_ids = [
            "table_group",
            "btn_take",
            "btn_pass",
            "settings_btn",
            "left_player",
            "bottom_player",
        ]

        self.assertEqual(
            screen.iter_midground_group_ids(),
            ("btn_take", "btn_pass", "settings_btn"),
        )
