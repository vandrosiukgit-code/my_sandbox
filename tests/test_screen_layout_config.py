import unittest

import screen_layout_config


class ScreenLayoutConfigTests(unittest.TestCase):
    def test_default_table_screen_layout_contains_action_button_placements(self):
        placements = screen_layout_config.DEFAULT_SCREEN_LAYOUT["screens"]["table_screen"]["groups"]

        self.assertEqual(
            placements["btn_take"],
            {
                "frame_id": "play_area_frame",
                "position": [870, 500],
            },
        )
        self.assertEqual(
            placements["btn_pass"],
            {
                "frame_id": "play_area_frame",
                "position": [1030, 500],
            },
        )
