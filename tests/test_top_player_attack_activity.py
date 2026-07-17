import json
import unittest
from pathlib import Path
from types import SimpleNamespace

import pygame

import group_config
from activities.player_attack_activity import PlayerAttackActivity
from activities.left_player_attack_activity import LeftPlayerAttackActivity
from activities.right_player_attack_activity import RightPlayerAttackActivity
from activities.top_player_attack_activity import TopPlayerAttackActivity
from core.game_controller import GameController
from game_screen.events import ActivityResult, VisualCommand
from group.group import Group
from screens.table_screen import TableScreen


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TopPlayerAttackActivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    @staticmethod
    def create_overlay_group():
        frames = []
        for _index in range(PlayerAttackActivity.EXPECTED_FRAME_COUNT):
            frame = pygame.Surface((2, 3), pygame.SRCALPHA)
            frame.set_at((0, 0), (255, 0, 0, 255))
            frames.append(frame)
        return Group(
            group_id="top_player_attack_overlay",
            rect=(0, 0, 2, 3),
            layers=({"name": "attack_overlay", "frames": frames, "position": (0, 0)},),
        )

    def test_top_activity_is_a_thin_player_attack_specialization(self):
        activity = TopPlayerAttackActivity(self.create_overlay_group())

        self.assertIsInstance(activity, PlayerAttackActivity)
        self.assertTrue(activity.flip_y)
        self.assertEqual(activity.rotation_degrees, 0.0)

    def test_top_activity_reflects_every_frame_across_horizontal_axis(self):
        group = self.create_overlay_group()

        activity = TopPlayerAttackActivity(group)
        activity.start_attack()

        for frame in group.get_layer_frames("attack_overlay"):
            self.assertEqual(frame.get_at((0, 2)), pygame.Color(255, 0, 0, 255))
            self.assertEqual(frame.get_at((0, 0)), pygame.Color(0, 0, 0, 0))

    def test_side_bot_activities_rotate_toward_the_table(self):
        left = LeftPlayerAttackActivity(self.create_overlay_group())
        right = RightPlayerAttackActivity(self.create_overlay_group())
        left.start_attack()
        right.start_attack()

        self.assertEqual(left.rotation_degrees, 270.0)
        self.assertEqual(right.rotation_degrees, 90.0)
        self.assertEqual(
            left.overlay_group.get_layer_frames("attack_overlay")[0].get_size(),
            (3, 2),
        )
        self.assertEqual(
            right.overlay_group.get_layer_frames("attack_overlay")[0].get_size(),
            (3, 2),
        )

    def test_top_overlay_reuses_bottom_resource_and_has_its_own_anchor(self):
        top = group_config.get_group_config("top_player_attack_overlay")
        bottom = group_config.get_group_config("bottom_player_attack_overlay")
        layout = json.loads(
            (PROJECT_ROOT / "assets" / "screen_layout.json").read_text(encoding="utf-8")
        )["screens"]["table_screen"]["groups"]

        self.assertEqual(top["layers"][0]["resource_key"], bottom["layers"][0]["resource_key"])
        self.assertEqual(top["hit_rect"], [0, 0, 0, 0])
        self.assertEqual(layout["top_player_attack_overlay"]["frame_id"], "top_player_portrait")
        self.assertEqual(layout["top_player_attack_overlay"]["position"], [-115, 0])

    def test_right_overlay_anchor_compensates_for_rotated_visible_content(self):
        layout = json.loads(
            (PROJECT_ROOT / "assets" / "screen_layout.json").read_text(encoding="utf-8")
        )["screens"]["table_screen"]["groups"]

        self.assertEqual(layout["right_player_attack_overlay"]["frame_id"], "right_player_portrait")
        self.assertEqual(layout["right_player_attack_overlay"]["position"], [-164, -61])

    def test_controller_builds_top_start_and_finish_commands(self):
        controller = GameController()
        idle = SimpleNamespace(attacker_id=None)
        active = SimpleNamespace(attacker_id="top_player_hand")

        start = controller.build_player_attack_transition_commands(idle, active)
        finish = controller.build_player_attack_transition_commands(active, idle)

        self.assertEqual([(command.type, command.target) for command in start], [
            ("player.attack.start", "player.top.attack"),
        ])
        self.assertEqual([(command.type, command.target) for command in finish], [
            ("player.attack.finish", "player.top.attack"),
        ])

    def test_controller_has_an_attack_target_for_every_player_and_bot(self):
        controller = GameController()

        self.assertEqual(set(controller.ATTACK_VISUAL_TARGETS), set(controller.PLAYER_ORDER))
        for player_id in controller.PLAYER_ORDER:
            commands = controller.build_player_attack_transition_commands(
                SimpleNamespace(attacker_id=None),
                SimpleNamespace(attacker_id=player_id),
            )
            self.assertEqual(len(commands), 1)
            self.assertEqual(commands[0].type, "player.attack.start")

    def test_initial_deal_completion_releases_the_actual_attack_command(self):
        controller = GameController()
        start_response = controller.start_game()
        attacker_id = start_response.state_view["attacker_id"]
        expected_target = controller.ATTACK_VISUAL_TARGETS[attacker_id][1]

        response = controller.handle_activity_result(
            ActivityResult(type="deal.completed", source="card_deal_sequence")
        )

        self.assertEqual(len(response.commands), 1)
        self.assertEqual(response.commands[0].type, "player.attack.start")
        self.assertEqual(response.commands[0].target, expected_target)

    def test_controller_finishes_bottom_before_starting_top(self):
        controller = GameController()
        bottom = SimpleNamespace(attacker_id="bottom_player_hand")
        top = SimpleNamespace(attacker_id="top_player_hand")

        commands = controller.build_player_attack_transition_commands(bottom, top)

        self.assertEqual(
            [(command.type, command.target) for command in commands],
            [
                ("player.attack.finish", "player.bottom.attack"),
                ("player.attack.start", "player.top.attack"),
            ],
        )

    def test_table_screen_routes_top_target_to_top_activity(self):
        screen = object.__new__(TableScreen)

        class AttackActivity:
            def start_attack(self):
                return 4

            def is_transition_complete(self, transition_id):
                return transition_id == 4

        activity = AttackActivity()
        watchers = []
        screen.get_named_activity = lambda activity_id: activity if activity_id == "top_player_attack" else None
        screen.register_activity_result_watcher = lambda **watcher: watchers.append(watcher)

        transition_id = screen.dispatch_visual_command(
            VisualCommand(
                type="player.attack.start",
                target="player.top.attack",
                command_id="attack.top.start",
            )
        )

        self.assertEqual(transition_id, 4)
        self.assertEqual(watchers[0]["result"].source, "top_player_attack")
        self.assertEqual(watchers[0]["result"].command_id, "attack.top.start")

    def test_table_screen_has_routes_for_every_attack_target(self):
        self.assertEqual(
            set(TableScreen.ATTACK_ACTIVITY_BY_TARGET),
            {target for _seat, target in GameController.ATTACK_VISUAL_TARGETS.values()},
        )


if __name__ == "__main__":
    unittest.main()
