import json
import unittest
from pathlib import Path
from types import SimpleNamespace

import pygame

import group_config
from activities.bottom_player_defense_activity import BottomPlayerDefenseActivity
from activities.left_player_defense_activity import LeftPlayerDefenseActivity
from activities.player_defense_activity import PlayerDefenseActivity
from activities.right_player_defense_activity import RightPlayerDefenseActivity
from activities.top_player_defense_activity import TopPlayerDefenseActivity
from core.game_controller import GameController
from game_screen.events import VisualCommand
from group.group import Group
from screens.table_screen import TableScreen


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class PlayerDefenseActivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        group_config.reload_group_config()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    @staticmethod
    def create_overlay_group(group_id="defense_overlay"):
        frames = []
        for _index in range(PlayerDefenseActivity.EXPECTED_FRAME_COUNT):
            frame = pygame.Surface((3, 2), pygame.SRCALPHA)
            frame.set_at((0, 0), (255, 0, 0, 255))
            frames.append(frame)
        return Group(
            group_id=group_id,
            rect=(0, 0, 3, 2),
            layers=({"name": "defense_overlay", "frames": frames, "position": (0, 0)},),
        )

    def test_seat_activities_are_thin_defense_specializations(self):
        bottom = BottomPlayerDefenseActivity(self.create_overlay_group("bottom"))
        top = TopPlayerDefenseActivity(self.create_overlay_group("top"))
        left = LeftPlayerDefenseActivity(self.create_overlay_group("left"))
        right = RightPlayerDefenseActivity(self.create_overlay_group("right"))

        self.assertTrue(all(isinstance(activity, PlayerDefenseActivity) for activity in (
            bottom,
            top,
            left,
            right,
        )))
        self.assertEqual(bottom.rotation_degrees, 0.0)
        self.assertEqual(top.rotation_degrees, 0.0)
        self.assertEqual(left.rotation_degrees, 0.0)
        self.assertEqual(right.rotation_degrees, 0.0)
        self.assertFalse(top.flip_y)
        self.assertFalse(left.flip_y)
        self.assertFalse(right.flip_y)
        self.assertTrue(all(activity.frame_duration == 0.10 for activity in (
            bottom,
            top,
            left,
            right,
        )))

    def test_idle_runtime_frame_is_fully_transparent(self):
        group = self.create_overlay_group()

        PlayerDefenseActivity(group)

        idle_frame = group.get_layer_frames("defense_overlay")[0]
        self.assertEqual(idle_frame.get_bounding_rect().size, (0, 0))

    def test_defense_groups_share_resource_and_portrait_local_anchor(self):
        layout = json.loads(
            (PROJECT_ROOT / "assets" / "screen_layout.json").read_text(encoding="utf-8")
        )["screens"]["table_screen"]["groups"]

        for seat in ("bottom", "right", "top", "left"):
            group_id = f"{seat}_player_defense_overlay"
            config = group_config.get_group_config(group_id)
            self.assertEqual(config["layers"][0]["resource_key"], "main_screen.player_defense.overlay")
            self.assertEqual(config["hit_rect"], [0, 0, 0, 0])
            self.assertEqual(layout[group_id]["frame_id"], f"{seat}_player_portrait")
            self.assertEqual(layout[group_id]["position"], [25, 25])

    def test_controller_builds_defense_start_and_finish_commands(self):
        controller = GameController()
        idle = SimpleNamespace(defender_id=None)
        active = SimpleNamespace(defender_id="right_player_hand")

        start = controller.build_player_defense_transition_commands(idle, active)
        finish = controller.build_player_defense_transition_commands(active, idle)

        self.assertEqual([(command.type, command.target) for command in start], [
            ("player.defense.start", "player.right.defense"),
        ])
        self.assertEqual([(command.type, command.target) for command in finish], [
            ("player.defense.finish", "player.right.defense"),
        ])

    def test_round_role_transition_keeps_defense_reaction_out_of_initial_queue(self):
        controller = GameController()
        previous = SimpleNamespace(
            attacker_id="bottom_player_hand",
            defender_id="right_player_hand",
        )
        current = SimpleNamespace(
            attacker_id="right_player_hand",
            defender_id="top_player_hand",
        )

        commands = controller.build_player_state_transition_commands(previous, current)

        self.assertEqual([command.type for command in commands], [
            "player.attack.finish",
            "player.attack.start",
        ])

    def test_controller_has_defense_target_for_every_player_and_bot(self):
        controller = GameController()

        self.assertEqual(set(controller.DEFENSE_VISUAL_TARGETS), set(controller.PLAYER_ORDER))

    def test_attack_event_queues_defense_after_card_animation(self):
        controller = GameController()
        snapshot = SimpleNamespace(
            attacker_id="bottom_player_hand",
            defender_id="right_player_hand",
        )
        domain_result = SimpleNamespace(
            events=(
                SimpleNamespace(
                    type="cards_attacked",
                    payload={
                        "player_id": "bottom_player_hand",
                        "card_ids": ("cards.6_of_hearts",),
                    },
                ),
            ),
            snapshot=snapshot,
        )

        card_commands = controller.build_commands_from_domain_result(domain_result, snapshot)
        defense_commands = controller.flush_pending_visual_commands()

        self.assertEqual(card_commands[0].type, "start_player_turn")
        self.assertEqual(defense_commands[0].type, "player.defense.start")
        self.assertEqual(defense_commands[0].target, "player.right.defense")

    def test_throw_in_event_also_builds_defense_reaction(self):
        controller = GameController()
        domain_result = SimpleNamespace(
            events=(SimpleNamespace(type="card_thrown_in"),),
            snapshot=SimpleNamespace(defender_id="left_player_hand"),
        )

        commands = controller.build_player_defense_reaction_commands(domain_result)

        self.assertEqual([(command.type, command.target) for command in commands], [
            ("player.defense.start", "player.left.defense"),
        ])

    def test_table_screen_routes_defense_command_to_defense_activity(self):
        screen = object.__new__(TableScreen)

        class DefenseActivity:
            def start_defense(self):
                return 6

            def is_transition_complete(self, transition_id):
                return transition_id == 6

        activity = DefenseActivity()
        watchers = []
        screen.get_named_activity = lambda activity_id: (
            activity if activity_id == "right_player_defense" else None
        )
        screen.register_activity_result_watcher = lambda **watcher: watchers.append(watcher)

        transition_id = screen.dispatch_visual_command(
            VisualCommand(
                type="player.defense.start",
                target="player.right.defense",
                command_id="defense.right.start",
            )
        )

        self.assertEqual(transition_id, 6)
        self.assertEqual(watchers[0]["result"].type, "player.defense.started")
        self.assertEqual(watchers[0]["result"].source, "right_player_defense")

    def test_table_screen_has_routes_for_every_defense_target(self):
        self.assertEqual(
            set(TableScreen.DEFENSE_ACTIVITY_BY_TARGET),
            {target for _seat, target in GameController.DEFENSE_VISUAL_TARGETS.values()},
        )

    def test_defense_groups_draw_above_player_portraits(self):
        screen = object.__new__(TableScreen)
        screen.active_group_ids = [
            "table_group",
            "bottom_player_defense_overlay",
            "bottom_player",
        ]

        self.assertNotIn("bottom_player_defense_overlay", screen.iter_midground_group_ids())
        self.assertIn("bottom_player_defense_overlay", screen.DEFENSE_FOREGROUND_GROUP_IDS)


if __name__ == "__main__":
    unittest.main()
