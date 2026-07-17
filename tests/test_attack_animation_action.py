import unittest

import pygame

from actions.attack_animation_action import AttackAnimationAction
from activities import PlayerAttackActivity
from group.group import Group


class TrackingLayer:
    def __init__(self, frame_index=0):
        self.current_frame_index = frame_index


class TrackingGroup:
    def __init__(self, frame_count=13, frame_index=0):
        self.id = "attack_overlay"
        self.frames = tuple(range(frame_count))
        self.layer = TrackingLayer(frame_index)
        self.frame_calls = []

    def get_layer_frames(self, layer_name):
        return self.frames

    def get_layer(self, layer_name):
        return self.layer

    def set_layer_frame(self, layer_name, frame_index):
        self.layer.current_frame_index = frame_index
        self.frame_calls.append(frame_index)


class AttackAnimationActionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_forward_action_is_finite_and_reaches_last_frame(self):
        group = TrackingGroup()
        action = AttackAnimationAction(
            group,
            start_frame_index=0,
            target_frame_index=12,
            frame_duration=0.01,
        )

        action.start()
        action.update(0.12)

        self.assertTrue(action.is_finished())
        self.assertEqual(action.current_frame_index, 12)
        self.assertEqual(group.frame_calls, list(range(1, 13)))

    def test_reverse_action_uses_the_same_frames_in_reverse(self):
        group = TrackingGroup(frame_index=12)
        action = AttackAnimationAction(
            group,
            start_frame_index=12,
            target_frame_index=0,
            frame_duration=0.01,
        )

        action.update(0.12)

        self.assertTrue(action.is_finished())
        self.assertEqual(group.frame_calls, list(range(11, -1, -1)))

    def test_cancel_stops_on_current_frame(self):
        group = TrackingGroup()
        action = AttackAnimationAction(
            group,
            start_frame_index=0,
            target_frame_index=12,
            frame_duration=0.01,
        )
        action.update(0.03)

        action.cancel()
        action.update(1.0)

        self.assertTrue(action.is_finished())
        self.assertEqual(action.current_frame_index, 3)
        self.assertEqual(group.layer.current_frame_index, 3)

    def test_action_rejects_a_non_animated_layer(self):
        with self.assertRaises(ValueError):
            AttackAnimationAction(
                TrackingGroup(frame_count=1),
                target_frame_index=0,
            )

    def test_player_activity_owns_the_finite_action(self):
        activity = PlayerAttackActivity(TrackingGroup())

        activity.start_attack()

        self.assertIsInstance(activity.current_action, AttackAnimationAction)
        self.assertFalse(activity.current_action.is_finished())
        activity.update(1.0)
        self.assertIsNone(activity.current_action)
        self.assertEqual(activity.state, "active")
        self.assertFalse(activity.is_finished())

    def test_player_activity_applies_local_position_and_rotation_once(self):
        frames = []
        for _index in range(PlayerAttackActivity.EXPECTED_FRAME_COUNT):
            frame = pygame.Surface((3, 2), pygame.SRCALPHA)
            frame.set_at((0, 0), (255, 0, 0, 255))
            frames.append(frame)
        group = Group(
            group_id="rotated_attack_overlay",
            rect=(0, 0, 3, 2),
            layers=({"name": "attack_overlay", "frames": frames, "position": (0, 0)},),
        )

        activity = PlayerAttackActivity(
            group,
            overlay_local_position=(7, 9),
            rotation_degrees=180,
        )
        self.assertEqual(
            group.get_layer_frames("attack_overlay")[0].get_at((0, 0)),
            pygame.Color(255, 0, 0, 255),
        )

        activity.start_attack()

        transformed = group.get_layer_frames("attack_overlay")[0]
        self.assertEqual(group.local_rect.topleft, (7, 9))
        self.assertEqual(transformed.get_size(), (3, 2))
        self.assertEqual(transformed.get_at((2, 1)), pygame.Color(255, 0, 0, 255))

        activity.finish_attack()
        self.assertEqual(
            group.get_layer_frames("attack_overlay")[0].get_at((2, 1)),
            pygame.Color(255, 0, 0, 255),
        )

    def test_player_activity_can_flip_frames_across_horizontal_axis(self):
        frames = []
        for _index in range(PlayerAttackActivity.EXPECTED_FRAME_COUNT):
            frame = pygame.Surface((2, 3), pygame.SRCALPHA)
            frame.set_at((0, 0), (255, 0, 0, 255))
            frames.append(frame)
        group = Group(
            group_id="flipped_attack_overlay",
            rect=(0, 0, 2, 3),
            layers=({"name": "attack_overlay", "frames": frames, "position": (0, 0)},),
        )

        activity = PlayerAttackActivity(group, flip_y=True)
        activity.start_attack()

        transformed = group.get_layer_frames("attack_overlay")[0]
        self.assertEqual(transformed.get_at((0, 2)), pygame.Color(255, 0, 0, 255))


if __name__ == "__main__":
    unittest.main()
