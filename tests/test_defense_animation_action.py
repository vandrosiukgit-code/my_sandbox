import unittest

import pygame

from actions.defense_animation_action import DefenseAnimationAction
from activities.player_defense_activity import PlayerDefenseActivity


class TrackingLayer:
    def __init__(self):
        self.current_frame_index = 0


class TrackingGroup:
    def __init__(self, frame_count=8):
        self.id = "defense_overlay"
        self.frames = tuple(
            pygame.Surface((1, 1), pygame.SRCALPHA)
            for _index in range(frame_count)
        )
        self.layer = TrackingLayer()
        self.calls = []

    def get_layer_frames(self, layer_name):
        return self.frames

    def get_layer(self, layer_name):
        return self.layer

    def set_layer_frames(self, layer_name, frames):
        self.frames = tuple(frames)

    def set_layer_frame(self, layer_name, frame_index):
        self.layer.current_frame_index = frame_index
        self.calls.append(frame_index)


class DefenseAnimationActionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_defense_contract_requires_eight_frames(self):
        with self.assertRaises(ValueError):
            DefenseAnimationAction(TrackingGroup(7), target_frame_index=6)

    def test_defense_cycle_uses_all_frames_and_holds_last_for_two_frames(self):
        group = TrackingGroup()
        action = DefenseAnimationAction(
            group,
            target_frame_index=7,
            frame_duration=0.01,
        )
        action.update(0.07)
        self.assertEqual(group.calls, list(range(1, 8)))
        self.assertEqual(action.phase, "holding")
        self.assertFalse(action.is_finished())

        action.update(0.019)
        self.assertEqual(action.phase, "holding")
        self.assertEqual(group.calls, list(range(1, 8)))

        action.update(0.001)
        self.assertEqual(action.phase, "returning")
        action.update(0.07)
        self.assertEqual(group.calls, [*range(1, 8), *range(6, -1, -1)])
        self.assertTrue(action.is_finished())

    def test_explicit_reverse_does_not_start_a_second_cycle(self):
        group = TrackingGroup()
        group.layer.current_frame_index = 5
        action = DefenseAnimationAction(
            group,
            start_frame_index=5,
            target_frame_index=0,
            frame_duration=0.01,
        )

        action.update(0.05)

        self.assertEqual(group.calls, [4, 3, 2, 1, 0])
        self.assertTrue(action.is_finished())

    def test_player_defense_activity_owns_defense_action(self):
        activity = PlayerDefenseActivity(TrackingGroup(), frame_duration=0.01)

        activity.start_defense()

        self.assertIsInstance(activity.current_action, DefenseAnimationAction)
        activity.update(0.07)
        self.assertEqual(activity.state, "entering")
        self.assertEqual(activity.current_frame_index, 7)

        activity.update(0.09)
        self.assertIsNone(activity.current_action)
        self.assertEqual(activity.current_frame_index, 0)
        self.assertEqual(activity.state, "idle")

    def test_finish_defense_reverses_an_in_progress_cycle_immediately(self):
        activity = PlayerDefenseActivity(TrackingGroup(), frame_duration=0.01)
        activity.start_defense()
        activity.update(0.03)

        transition_id = activity.finish_defense()
        activity.update(0.03)

        self.assertEqual(activity.current_frame_index, 0)
        self.assertEqual(activity.state, "idle")
        self.assertTrue(activity.is_transition_complete(transition_id))


if __name__ == "__main__":
    unittest.main()
