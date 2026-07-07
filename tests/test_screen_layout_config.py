import unittest

import screen_layout_config


class ScreenLayoutConfigTests(unittest.TestCase):
    def test_default_table_screen_layout_contains_take_button_placement(self):
        placements = screen_layout_config.DEFAULT_SCREEN_LAYOUT["screens"]["table_screen"]["groups"]

        self.assertEqual(
            placements["take_btn"],
            {
                "frame_id": "game_table",
                "position": [980, 500],
            },
        )

