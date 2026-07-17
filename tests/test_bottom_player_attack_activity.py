import json
import unittest
from pathlib import Path
from types import SimpleNamespace

import pygame

import group_config
from activities.bottom_player_attack_activity import BottomPlayerAttackActivity
from core.game_controller import GameController
from game_screen.events import VisualCommand
from group.group import Group
from screens.table_screen import TableScreen


class TrackingLayer:
    def __init__(self):
        self.current_frame_index = 0


class TrackingGroup:
    def __init__(self, frame_counts=None):
        self.id = "bottom_player_attack_overlay"
        if frame_counts is None:
            frame_counts = {
                layer_name: BottomPlayerAttackActivity.EXPECTED_FRAME_COUNT
                for layer_name in BottomPlayerAttackActivity.LAYER_NAMES
            }
        self.frames = {
            layer_name: tuple(range(frame_count))
            for layer_name, frame_count in frame_counts.items()
        }
        self.layers = {
            layer_name: TrackingLayer()
            for layer_name in frame_counts
        }
        self.frame_calls = []

    def get_layer_frames(self, layer_name):
        return self.frames[layer_name]

    def set_layer_frame(self, layer_name, frame_index):
        self.layers[layer_name].current_frame_index = frame_index
        self.frame_calls.append((layer_name, frame_index))

    def get_layer(self, layer_name):
        return self.layers[layer_name]


class BottomPlayerAttackActivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    @staticmethod
    def create_overlay_group():
        frames = [
            pygame.Surface((8, 8), pygame.SRCALPHA)
            for _index in range(BottomPlayerAttackActivity.EXPECTED_FRAME_COUNT)
        ]
        return Group(
            group_id="bottom_player_attack_overlay",
            rect=(0, 0, 1024, 768),
            layers=tuple(
                {"name": layer_name, "frames": frames, "position": (0, 0)}
                for layer_name in BottomPlayerAttackActivity.LAYER_NAMES
            ),
        )

    @staticmethod
    def create_tracking_activity(frame_duration=0.01, frame_counts=None):
        group = TrackingGroup(frame_counts=frame_counts)
        return BottomPlayerAttackActivity(group, frame_duration=frame_duration), group

    def test_activity_declares_one_overlay_animation_layer(self):
        self.assertEqual(BottomPlayerAttackActivity.LAYER_NAMES, ("attack_overlay",))
        self.assertEqual(BottomPlayerAttackActivity.EXPECTED_FRAME_COUNT, 13)

    def test_six_added_frames_preserve_the_transition_duration(self):
        activity = BottomPlayerAttackActivity(TrackingGroup())

        self.assertAlmostEqual(
            activity.frame_duration * (activity.frame_count - 1),
            0.54,
            places=6,
        )

    def test_attack_layer_is_not_baked_into_the_player_group(self):
        player_attack_layers = tuple(
            layer["name"]
            for layer in group_config.get_group_config("bottom_player")["layers"]
            if layer["name"].startswith("attack_")
        )
        overlay_layers = tuple(
            layer["name"]
            for layer in group_config.get_group_config("bottom_player_attack_overlay")["layers"]
        )

        self.assertEqual(player_attack_layers, ())
        self.assertEqual(overlay_layers, ("attack_overlay",))

    def test_overlay_is_non_interactive_and_bounded_around_portrait(self):
        overlay = group_config.get_group_config("bottom_player_attack_overlay")
        layout_path = Path(__file__).resolve().parents[1] / "assets" / "screen_layout.json"
        layout = json.loads(layout_path.read_text(encoding="utf-8"))
        placement = layout["screens"]["table_screen"]["groups"]["bottom_player_attack_overlay"]

        self.assertEqual(overlay["hit_rect"], [0, 0, 0, 0])
        self.assertEqual(placement["frame_id"], "bottom_player_portrait")
        scaled_width = overlay["rect"][2] * overlay["scale_factor"]
        scaled_height = overlay["rect"][3] * overlay["scale_factor"]
        self.assertLessEqual(scaled_width, 440)
        self.assertLessEqual(scaled_height, 330)
        self.assertAlmostEqual(placement["position"][0] + scaled_width / 2, 100, delta=6)
        self.assertAlmostEqual(placement["position"][1] + scaled_height, 200, delta=6)

    def test_constructor_rejects_different_frame_counts(self):
        layer_names = BottomPlayerAttackActivity.LAYER_NAMES
        frame_counts = {layer_name: 6 for layer_name in layer_names}

        with self.assertRaises(ValueError):
            BottomPlayerAttackActivity(TrackingGroup(frame_counts), frame_duration=0.01)

    def test_constructor_rejects_less_than_two_frames(self):
        frame_counts = {
            layer_name: 1
            for layer_name in BottomPlayerAttackActivity.LAYER_NAMES
        }

        with self.assertRaises(ValueError):
            BottomPlayerAttackActivity(TrackingGroup(frame_counts), frame_duration=0.01)

    def test_constructor_rejects_missing_required_layer(self):
        frame_counts = {
            layer_name: BottomPlayerAttackActivity.EXPECTED_FRAME_COUNT
            for layer_name in BottomPlayerAttackActivity.LAYER_NAMES[:-1]
        }

        with self.assertRaises((KeyError, ValueError)):
            BottomPlayerAttackActivity(TrackingGroup(frame_counts), frame_duration=0.01)

    def test_frame_duration_has_a_positive_lower_bound(self):
        activity, _group = self.create_tracking_activity(frame_duration=-10)

        self.assertGreater(activity.frame_duration, 0)

    def test_start_selects_idle_frame_without_finishing_long_lived_activity(self):
        activity, group = self.create_tracking_activity()

        activity.start()

        self.assertEqual(activity.current_frame_index, 0)
        self.assertEqual(activity.state, "idle")
        self.assertFalse(activity.is_finished())
        self.assertTrue(all(layer.current_frame_index == 0 for layer in group.layers.values()))

    def test_update_before_explicit_start_initializes_activity(self):
        activity, _group = self.create_tracking_activity()

        activity.update(0)

        self.assertTrue(activity.started)
        self.assertEqual(activity.current_frame_index, 0)

    def test_forward_transition_visits_every_frame_exactly_in_order(self):
        activity, group = self.create_tracking_activity()
        primary_layer = activity.LAYER_NAMES[0]

        transition_id = activity.start_attack()
        for _index in range(1, activity.frame_count):
            activity.update(activity.frame_duration)

        visited = [
            frame_index
            for layer_name, frame_index in group.frame_calls
            if layer_name == primary_layer
        ]
        self.assertEqual(visited, list(range(activity.frame_count)))
        self.assertEqual(activity.state, "active")
        self.assertTrue(activity.is_transition_complete(transition_id))

    def test_reverse_transition_visits_every_frame_exactly_in_order(self):
        activity, group = self.create_tracking_activity()
        primary_layer = activity.LAYER_NAMES[0]
        activity.start_attack()
        activity.update(activity.frame_duration * (activity.frame_count - 1))
        group.frame_calls.clear()

        transition_id = activity.finish_attack()
        for _index in range(activity.frame_count - 1):
            activity.update(activity.frame_duration)

        visited = [
            frame_index
            for layer_name, frame_index in group.frame_calls
            if layer_name == primary_layer
        ]
        self.assertEqual(visited, list(range(activity.frame_count - 2, -1, -1)))
        self.assertEqual(activity.state, "idle")
        self.assertTrue(activity.is_transition_complete(transition_id))

    def test_sub_frame_updates_accumulate_without_early_frame_change(self):
        activity, _group = self.create_tracking_activity(frame_duration=0.1)
        activity.start_attack()

        activity.update(0.04)
        activity.update(0.05)
        self.assertEqual(activity.current_frame_index, 0)

        activity.update(0.01)
        self.assertEqual(activity.current_frame_index, 1)

    def test_zero_and_negative_dt_do_not_change_frame(self):
        activity, _group = self.create_tracking_activity()
        activity.start_attack()

        activity.update(0)
        activity.update(-100)

        self.assertEqual(activity.current_frame_index, 0)
        self.assertTrue(activity.transition_active)

    def test_large_dt_reaches_target_without_overshooting(self):
        activity, _group = self.create_tracking_activity()
        transition_id = activity.start_attack()

        activity.update(1000)

        self.assertEqual(activity.current_frame_index, activity.frame_count - 1)
        self.assertEqual(activity.state, "active")
        self.assertFalse(activity.transition_active)
        self.assertTrue(activity.is_transition_complete(transition_id))

    def test_completion_is_reported_only_after_target_frame(self):
        activity, _group = self.create_tracking_activity()
        transition_id = activity.start_attack()

        activity.update(activity.frame_duration * (activity.frame_count - 2))
        self.assertFalse(activity.is_transition_complete(transition_id))

        activity.update(activity.frame_duration)
        self.assertTrue(activity.is_transition_complete(transition_id))

    def test_finish_attack_reverses_from_every_intermediate_frame(self):
        for intermediate_frame in range(1, BottomPlayerAttackActivity.EXPECTED_FRAME_COUNT):
            with self.subTest(intermediate_frame=intermediate_frame):
                activity, _group = self.create_tracking_activity()
                activity.start_attack()
                activity.update(activity.frame_duration * intermediate_frame)

                transition_id = activity.finish_attack()
                activity.update(activity.frame_duration * intermediate_frame)

                self.assertEqual(activity.current_frame_index, 0)
                self.assertEqual(activity.state, "idle")
                self.assertTrue(activity.is_transition_complete(transition_id))

    def test_start_attack_reverses_from_every_intermediate_exit_frame(self):
        for exit_steps in range(1, BottomPlayerAttackActivity.EXPECTED_FRAME_COUNT):
            with self.subTest(exit_steps=exit_steps):
                activity, _group = self.create_tracking_activity()
                activity.start_attack()
                activity.update(1000)
                activity.finish_attack()
                activity.update(activity.frame_duration * exit_steps)
                frame_before_reverse = activity.current_frame_index

                transition_id = activity.start_attack()
                last_frame = activity.frame_count - 1
                activity.update(activity.frame_duration * (last_frame - frame_before_reverse))

                self.assertEqual(activity.current_frame_index, last_frame)
                self.assertEqual(activity.state, "active")
                self.assertTrue(activity.is_transition_complete(transition_id))

    def test_start_attack_reverses_an_in_progress_exit_without_frame_jump(self):
        activity, _group = self.create_tracking_activity()
        activity.start_attack()
        activity.update(activity.frame_duration * (activity.frame_count - 1))
        activity.finish_attack()
        activity.update(activity.frame_duration * 2)
        before_reverse = activity.current_frame_index

        transition_id = activity.start_attack()

        self.assertEqual(activity.current_frame_index, before_reverse)
        remaining_steps = activity.frame_count - 1 - before_reverse
        activity.update(activity.frame_duration * remaining_steps)
        self.assertEqual(activity.current_frame_index, activity.frame_count - 1)
        self.assertTrue(activity.is_transition_complete(transition_id))

    def test_repeated_start_command_is_idempotent(self):
        activity, _group = self.create_tracking_activity()
        first_transition_id = activity.start_attack()
        activity.update(activity.frame_duration / 2)
        elapsed_before_repeat = activity.frame_elapsed

        repeated_transition_id = activity.start_attack()

        self.assertEqual(repeated_transition_id, first_transition_id)
        self.assertEqual(activity.frame_elapsed, elapsed_before_repeat)

    def test_repeated_command_in_completed_state_does_not_create_new_transition(self):
        activity, _group = self.create_tracking_activity()
        transition_id = activity.start_attack()
        activity.update(1000)

        self.assertEqual(activity.start_attack(), transition_id)
        self.assertEqual(activity.state, "active")

    def test_repeated_finish_command_is_idempotent(self):
        activity, _group = self.create_tracking_activity()
        activity.start_attack()
        activity.update(1000)
        transition_id = activity.finish_attack()
        activity.update(1000)

        self.assertEqual(activity.finish_attack(), transition_id)
        self.assertEqual(activity.state, "idle")

    def test_completed_transition_remains_complete_after_direction_changes(self):
        activity, _group = self.create_tracking_activity()
        entering_id = activity.start_attack()
        activity.update(1000)
        exiting_id = activity.finish_attack()

        self.assertTrue(activity.is_transition_complete(entering_id))
        self.assertFalse(activity.is_transition_complete(exiting_id))

        activity.update(1000)
        self.assertTrue(activity.is_transition_complete(entering_id))
        self.assertTrue(activity.is_transition_complete(exiting_id))

    def test_fixture_can_update_frame_duration_without_allowing_zero(self):
        activity, _group = self.create_tracking_activity(frame_duration=0.2)

        activity.apply_fixture({"frame_duration": 0.05})
        self.assertEqual(activity.frame_duration, 0.05)

        activity.apply_fixture({"frame_duration": 0})
        self.assertGreater(activity.frame_duration, 0)

    def test_apply_frame_clamps_both_ends(self):
        activity, _group = self.create_tracking_activity()

        activity.apply_frame(-100)
        self.assertEqual(activity.current_frame_index, 0)

        activity.apply_frame(100)
        self.assertEqual(activity.current_frame_index, activity.frame_count - 1)

    def test_finish_resets_frame_state_and_transition(self):
        activity, group = self.create_tracking_activity()
        activity.start_attack()
        activity.update(activity.frame_duration * 3)

        activity.finish()

        self.assertEqual(activity.current_frame_index, 0)
        self.assertEqual(activity.state, "idle")
        self.assertFalse(activity.transition_active)
        self.assertTrue(all(layer.current_frame_index == 0 for layer in group.layers.values()))

    def test_forward_and_reverse_transitions_share_the_same_frames(self):
        group = self.create_overlay_group()
        activity = BottomPlayerAttackActivity(group, frame_duration=0.01)

        entering_id = activity.start_attack()
        activity.update(activity.frame_duration * (activity.frame_count - 1))

        self.assertEqual(activity.state, "active")
        self.assertEqual(activity.current_frame_index, activity.frame_count - 1)
        self.assertTrue(activity.is_transition_complete(entering_id))

        exiting_id = activity.finish_attack()
        activity.update(activity.frame_duration * (activity.frame_count - 1))

        self.assertEqual(activity.state, "idle")
        self.assertEqual(activity.current_frame_index, 0)
        self.assertTrue(activity.is_transition_complete(exiting_id))
        for layer_name in activity.LAYER_NAMES:
            self.assertEqual(group.get_layer(layer_name).current_frame_index, 0)

    def test_finish_attack_can_reverse_an_in_progress_entry(self):
        activity = BottomPlayerAttackActivity(self.create_overlay_group(), frame_duration=0.01)

        activity.start_attack()
        activity.update(0.02)
        self.assertEqual(activity.current_frame_index, 2)

        transition_id = activity.finish_attack()
        activity.update(0.02)

        self.assertEqual(activity.state, "idle")
        self.assertEqual(activity.current_frame_index, 0)
        self.assertTrue(activity.is_transition_complete(transition_id))

    def test_controller_emits_transition_only_when_bottom_attacker_changes(self):
        controller = GameController()
        idle = SimpleNamespace(attacker_id="right_player_hand")
        active = SimpleNamespace(attacker_id=controller.HUMAN_PLAYER_ID)

        start_command = controller.build_bottom_player_attack_transition_command(idle, active)
        finish_command = controller.build_bottom_player_attack_transition_command(active, idle)

        self.assertEqual(start_command.type, "player.attack.start")
        self.assertEqual(finish_command.type, "player.attack.finish")
        self.assertIsNone(controller.build_bottom_player_attack_transition_command(active, active))

    def test_controller_transition_command_uses_public_target_and_is_blocking(self):
        controller = GameController()
        idle = SimpleNamespace(attacker_id="right_player_hand")
        active = SimpleNamespace(attacker_id=controller.HUMAN_PLAYER_ID)

        command = controller.build_bottom_player_attack_transition_command(idle, active)

        self.assertEqual(command.target, "player.bottom.attack")
        self.assertEqual(command.command_id, "game.player.bottom.attack.start")
        self.assertTrue(command.blocking)

    def test_controller_does_not_emit_transition_for_other_attackers(self):
        controller = GameController()
        right = SimpleNamespace(attacker_id="right_player_hand")
        left = SimpleNamespace(attacker_id="left_player_hand")

        self.assertIsNone(controller.build_bottom_player_attack_transition_command(right, left))

    def test_controller_emits_initial_start_when_bottom_is_first_attacker(self):
        controller = GameController()
        active = SimpleNamespace(attacker_id=controller.HUMAN_PLAYER_ID)

        command = controller.build_bottom_player_attack_transition_command(None, active)

        self.assertEqual(command.type, "player.attack.start")

    def test_table_screen_registers_completion_result_for_reverse_transition(self):
        screen = object.__new__(TableScreen)

        class AttackActivity:
            def finish_attack(self):
                return 12

            def is_transition_complete(self, transition_id):
                return transition_id == 12

        activity = AttackActivity()
        watchers = []
        screen.get_named_activity = lambda activity_id: activity if activity_id == "bottom_player_attack" else None
        screen.register_activity_result_watcher = lambda **watcher: watchers.append(watcher)

        transition_id = screen.dispatch_visual_command(
            VisualCommand(type="player.attack.finish", command_id="attack.finish")
        )

        self.assertEqual(transition_id, 12)
        self.assertEqual(watchers[0]["result"].type, "player.attack.finished")
        self.assertEqual(watchers[0]["result"].payload["state"], "idle")
        self.assertTrue(watchers[0]["completion_check"](activity))

    def test_table_screen_registers_completion_result_for_forward_transition(self):
        screen = object.__new__(TableScreen)

        class AttackActivity:
            def start_attack(self):
                return 8

            def is_transition_complete(self, transition_id):
                return transition_id == 8

        activity = AttackActivity()
        watchers = []
        screen.get_named_activity = lambda activity_id: activity if activity_id == "bottom_player_attack" else None
        screen.register_activity_result_watcher = lambda **watcher: watchers.append(watcher)

        transition_id = screen.dispatch_visual_command(
            VisualCommand(type="player.attack.start", command_id="attack.start")
        )

        self.assertEqual(transition_id, 8)
        self.assertEqual(watchers[0]["result"].type, "player.attack.started")
        self.assertEqual(watchers[0]["result"].source, "bottom_player_attack")
        self.assertEqual(watchers[0]["result"].command_id, "attack.start")
        self.assertEqual(watchers[0]["result"].payload["state"], "active")
        self.assertTrue(watchers[0]["completion_check"](activity))

    def test_repeated_screen_command_does_not_register_duplicate_watcher(self):
        screen = object.__new__(TableScreen)

        class AttackActivity:
            def start_attack(self):
                return 8

            def is_transition_complete(self, transition_id):
                return transition_id == 8

        activity = AttackActivity()
        watchers = []
        screen.get_named_activity = lambda activity_id: activity if activity_id == "bottom_player_attack" else None
        screen.register_activity_result_watcher = lambda **watcher: watchers.append(watcher)
        command = VisualCommand(type="player.attack.start", command_id="attack.start")

        screen.dispatch_visual_command(command)
        screen.dispatch_visual_command(command)

        self.assertEqual(len(watchers), 1)

    def test_table_screen_does_not_register_watcher_without_attack_activity(self):
        screen = object.__new__(TableScreen)
        watchers = []
        screen.get_named_activity = lambda _activity_id: None
        screen.register_activity_result_watcher = lambda **watcher: watchers.append(watcher)

        transition_id = screen.dispatch_visual_command(VisualCommand(type="player.attack.start"))

        self.assertIsNone(transition_id)
        self.assertEqual(watchers, [])

    def test_activity_completion_watcher_forwards_result_exactly_once(self):
        screen = object.__new__(TableScreen)
        screen._activity_result_watchers = []
        completed = {"value": False}
        activity = object()
        forwarded = []
        dispatched = []
        screen.forward_activity_result_to_controller = lambda result: forwarded.append(result.type) or ()
        screen.dispatch_visual_commands = lambda commands: dispatched.append(tuple(commands))
        result = SimpleNamespace(type="player.attack.started")
        screen.register_activity_result_watcher(
            activity,
            result,
            completion_check=lambda _activity: completed["value"],
        )

        screen.forward_activity_completion_results()
        self.assertEqual(forwarded, [])

        completed["value"] = True
        screen.forward_activity_completion_results()
        screen.forward_activity_completion_results()

        self.assertEqual(forwarded, ["player.attack.started"])
        self.assertEqual(len(dispatched), 1)

    def test_failed_completion_check_keeps_watcher_pending(self):
        screen = object.__new__(TableScreen)
        screen._activity_result_watchers = []
        screen.forward_activity_result_to_controller = lambda _result: self.fail("Result must not be forwarded")
        screen.dispatch_visual_commands = lambda _commands: None
        screen.register_activity_result_watcher(
            object(),
            SimpleNamespace(type="player.attack.started"),
            completion_check=lambda _activity: (_ for _ in ()).throw(RuntimeError("not ready")),
        )

        screen.forward_activity_completion_results()

        self.assertEqual(len(screen._activity_result_watchers), 1)
