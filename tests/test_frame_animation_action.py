import unittest

from actions.frame_animation_action import FrameAnimationAction


class TrackingLayer:
    def __init__(self, frame_index=0):
        self.current_frame_index = frame_index


class TrackingGroup:
    def __init__(self, frame_counts, frame_index=0):
        self.id = "frame_overlay"
        self.frames = {
            layer_name: tuple(range(frame_count))
            for layer_name, frame_count in frame_counts.items()
        }
        self.layers = {
            layer_name: TrackingLayer(frame_index)
            for layer_name in frame_counts
        }
        self.calls = []

    def get_layer_frames(self, layer_name):
        return self.frames[layer_name]

    def get_layer(self, layer_name):
        return self.layers[layer_name]

    def set_layer_frame(self, layer_name, frame_index):
        self.layers[layer_name].current_frame_index = frame_index
        self.calls.append((layer_name, frame_index))


class FrameAnimationActionTests(unittest.TestCase):
    def create_action(self, group=None, **overrides):
        group = group or TrackingGroup({"first": 4, "second": 4})
        kwargs = {
            "layer_names": ("first", "second"),
            "start_frame_index": 0,
            "target_frame_index": 3,
            "frame_duration": 0.1,
        }
        kwargs.update(overrides)
        return FrameAnimationAction(group, **kwargs), group

    def test_forward_transition_keeps_layers_synchronized_and_finishes(self):
        action, group = self.create_action()

        action.update(0.3)

        self.assertTrue(action.is_finished())
        self.assertEqual(action.current_frame_index, 3)
        self.assertEqual(group.layers["first"].current_frame_index, 3)
        self.assertEqual(group.layers["second"].current_frame_index, 3)

    def test_reverse_transition_uses_the_same_indices(self):
        group = TrackingGroup({"first": 4, "second": 4}, frame_index=3)
        action, _group = self.create_action(
            group,
            start_frame_index=3,
            target_frame_index=0,
        )

        action.update(0.3)

        first_layer_calls = [index for layer, index in group.calls if layer == "first"]
        self.assertEqual(first_layer_calls, [2, 1, 0])
        self.assertTrue(action.is_finished())

    def test_sub_frame_and_non_positive_updates_do_not_advance(self):
        action, _group = self.create_action()

        action.update(-1)
        action.update(0)
        action.update(0.099)

        self.assertEqual(action.current_frame_index, 0)
        self.assertFalse(action.is_finished())

    def test_large_update_reaches_target_without_overshoot(self):
        action, _group = self.create_action()

        action.update(100)

        self.assertEqual(action.current_frame_index, 3)
        self.assertTrue(action.is_finished())

    def test_cancel_preserves_current_frame(self):
        action, group = self.create_action()
        action.update(0.1)

        action.cancel()
        action.update(10)

        self.assertEqual(action.current_frame_index, 1)
        self.assertEqual(group.layers["first"].current_frame_index, 1)
        self.assertTrue(action.is_finished())

    def test_equal_start_and_target_finishes_on_start(self):
        action, _group = self.create_action(target_frame_index=0)

        action.start()

        self.assertTrue(action.is_finished())

    def test_indices_are_clamped_to_available_frames(self):
        action, _group = self.create_action(start_frame_index=-9, target_frame_index=99)

        self.assertEqual(action.current_frame_index, 0)
        self.assertEqual(action.target_frame_index, 3)

    def test_rejects_empty_mismatched_and_single_frame_layers(self):
        with self.assertRaises(ValueError):
            self.create_action(layer_names=())
        with self.assertRaises(ValueError):
            self.create_action(TrackingGroup({"first": 4, "second": 3}))
        with self.assertRaises(ValueError):
            FrameAnimationAction(
                TrackingGroup({"first": 1}),
                layer_names=("first",),
                target_frame_index=0,
            )

    def test_optional_expected_frame_count_is_enforced(self):
        with self.assertRaises(ValueError):
            self.create_action(expected_frame_count=5)

    def test_optional_hold_and_return_complete_one_finite_cycle(self):
        action, group = self.create_action(
            hold_frame_count=2,
            return_frame_index=0,
        )

        action.update(0.3)
        self.assertEqual(action.current_frame_index, 3)
        self.assertEqual(action.phase, "holding")
        self.assertFalse(action.is_finished())

        action.update(0.199)
        self.assertEqual(action.phase, "holding")
        action.update(0.001)
        self.assertEqual(action.phase, "returning")
        self.assertEqual(action.current_frame_index, 3)

        action.update(0.3)
        first_layer_calls = [index for layer, index in group.calls if layer == "first"]
        self.assertEqual(first_layer_calls, [1, 2, 3, 2, 1, 0])
        self.assertTrue(action.is_finished())


if __name__ == "__main__":
    unittest.main()
