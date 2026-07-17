import unittest

import pygame

from activities.take_button_activity import TakeButtonActivity
from game_screen.events import ScreenInputEvent
from group.group import Group


class TakeButtonActivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def create_button_group(self):
        surface = pygame.Surface((20, 20), pygame.SRCALPHA)
        surface.fill((240, 180, 40, 255))
        return Group(
            group_id="btn_take",
            rect=(0, 0, 20, 20),
            layers=(
                {
                    "name": "graphic_layer_1",
                    "frames": [surface],
                    "position": (0, 0),
                },
            ),
        )

    def test_activity_starts_in_disabled_visual_state_by_default(self):
        group = self.create_button_group()

        activity = TakeButtonActivity(group)
        activity.start()

        self.assertFalse(activity.enabled)
        self.assertAlmostEqual(group.scale_factor, activity.disabled_scale)
        self.assertIsNot(group.get_primary_layer_frames()[0], activity.enabled_frames[0])

    def test_disabled_button_consumes_click_without_press_animation(self):
        group = self.create_button_group()
        activity = TakeButtonActivity(group, enabled=False)
        activity.start()

        forwarded = activity.handle_input(
            ScreenInputEvent(type="click", button="left", group_id="btn_take")
        )

        self.assertFalse(forwarded)
        self.assertIsNone(activity.current_action)
        self.assertAlmostEqual(group.scale_factor, activity.disabled_scale)

    def test_enabled_click_starts_press_and_locks_until_state_sync(self):
        group = self.create_button_group()
        activity = TakeButtonActivity(group, enabled=True, press_duration=0.2)
        activity.start()

        forwarded = activity.handle_input(
            ScreenInputEvent(type="click", button="left", group_id="btn_take")
        )

        self.assertTrue(forwarded)
        self.assertTrue(activity.locked)
        self.assertIsNotNone(activity.current_action)

        activity.update(0.2)

        self.assertIsNone(activity.current_action)
        self.assertAlmostEqual(group.scale_factor, activity.disabled_scale)

        activity.set_enabled(True)

        self.assertFalse(activity.locked)
        self.assertAlmostEqual(group.scale_factor, activity.enabled_scale)
