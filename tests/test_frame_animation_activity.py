import unittest

import pygame

from actions.frame_animation_action import FrameAnimationAction
from activities.frame_animation_activity import FrameAnimationActivity
from group.group import Group


class FrameAnimationActivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    @staticmethod
    def create_group(frame_count=3):
        frames = []
        for _index in range(frame_count):
            frame = pygame.Surface((3, 2), pygame.SRCALPHA)
            frame.set_at((0, 0), (255, 0, 0, 255))
            frames.append(frame)
        return Group(
            group_id="frame_overlay",
            rect=(0, 0, 3, 2),
            layers=({"name": "overlay", "frames": frames, "position": (0, 0)},),
        )

    def create_activity(self, group=None, **overrides):
        kwargs = {
            "action_class": FrameAnimationAction,
            "layer_names": ("overlay",),
            "expected_frame_count": 3,
            "frame_duration": 0.1,
        }
        kwargs.update(overrides)
        return FrameAnimationActivity(group or self.create_group(), **kwargs)

    def test_activity_owns_finite_action_but_remains_long_lived(self):
        activity = self.create_activity()

        transition_id = activity.start_transition()
        self.assertIsInstance(activity.current_action, FrameAnimationAction)
        activity.update(0.2)

        self.assertIsNone(activity.current_action)
        self.assertEqual(activity.state, "active")
        self.assertTrue(activity.is_transition_complete(transition_id))
        self.assertFalse(activity.is_finished())

    def test_reverse_interrupt_starts_from_current_frame_without_jump(self):
        activity = self.create_activity()
        activity.start_transition()
        activity.update(0.1)
        frame_before_reverse = activity.current_frame_index

        activity.finish_transition()

        self.assertEqual(activity.current_frame_index, frame_before_reverse)
        activity.update(0.1)
        self.assertEqual(activity.current_frame_index, 0)
        self.assertEqual(activity.state, "idle")

    def test_local_position_is_applied_without_transforming_in_base_activity(self):
        group = self.create_group()

        self.create_activity(
            group,
            overlay_local_position=(7, 9),
        )

        frame = group.get_layer_frames("overlay")[0]
        self.assertEqual(group.local_rect.topleft, (7, 9))
        self.assertEqual(frame.get_at((0, 0)), pygame.Color(255, 0, 0, 255))

    def test_expected_frame_count_is_validated_by_activity_layer(self):
        with self.assertRaises(ValueError):
            self.create_activity(self.create_group(frame_count=2))


if __name__ == "__main__":
    unittest.main()
