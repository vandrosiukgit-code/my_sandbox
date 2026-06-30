"""Automated contracts for P0/P1 GUI layout diagnostics."""

import unittest

from tools.gui_geometry_report import (
    apply_candidate_rects,
    build_screen,
    collect_objects,
    detect_geometry_issues,
    prepare_collision_test_state,
)


def make_object(key, x, y, width, height, kind="frame", object_id=None):
    return {
        "key": key,
        "kind": kind,
        "id": object_id or key.split(":", 1)[-1],
        "rect": {"x": x, "y": y, "width": width, "height": height},
    }


class GuiGeometryReportTests(unittest.TestCase):
    def setUp(self):
        self.screen_size = (100, 100)
        self.deck = make_object("frame:deck_frame", 70, 10, 20, 20, object_id="deck_frame")
        self.slot = make_object(
            "frame:cards_slot_frame_1",
            80,
            15,
            15,
            15,
            object_id="cards_slot_frame_1",
        )

    def test_p1_contains_exact_intersection_parameters(self):
        outside, overlaps = detect_geometry_issues([self.deck, self.slot], self.screen_size)

        self.assertEqual(outside, [])
        self.assertEqual(len(overlaps), 1)
        self.assertEqual(overlaps[0]["severity"], "P1")
        self.assertEqual(overlaps[0]["intersection"], {"x": 80, "y": 15, "width": 10, "height": 15, "left": 80, "top": 15, "right": 90, "bottom": 30, "center": [85, 22]})
        self.assertEqual(overlaps[0]["area"], 150)

    def test_p0_contains_object_and_screen_parameters(self):
        deck_outside_screen = make_object("frame:deck_frame", 90, 10, 20, 20, object_id="deck_frame")

        outside, overlaps = detect_geometry_issues([deck_outside_screen], self.screen_size)

        self.assertEqual(overlaps, [])
        self.assertEqual(outside[0]["severity"], "P0")
        self.assertEqual(outside[0]["outside_area"], 200)
        self.assertEqual(outside[0]["rect"]["right"], 110)
        self.assertEqual(outside[0]["visible_rect"]["right"], 100)

    def test_session_allowlist_can_ignore_object_or_specific_pair(self):
        objects = [self.deck, self.slot]

        _, ignored_by_object = detect_geometry_issues(
            objects,
            self.screen_size,
            ignored_collision_keys=(self.slot["key"],),
        )
        _, ignored_by_pair = detect_geometry_issues(
            objects,
            self.screen_size,
            ignored_collision_pairs=((self.deck["key"], self.slot["key"]),),
        )

        self.assertEqual(ignored_by_object, [])
        self.assertEqual(ignored_by_pair, [])

    def test_candidate_rect_is_applied_without_mutating_original_snapshot(self):
        candidate_objects = apply_candidate_rects(
            [self.deck],
            {self.deck["key"]: (10, 20, 30, 40)},
        )

        self.assertEqual(candidate_objects[0]["rect"]["x"], 10)
        self.assertEqual(candidate_objects[0]["rect"]["width"], 30)
        self.assertEqual(self.deck["rect"]["x"], 70)

    def test_groups_from_one_activity_can_overlap(self):
        deck_back = make_object("activity_group:deck_frame.card_back", 20, 20, 20, 20, kind="activity_group")
        trump = make_object("activity_group:deck_frame.trump", 20, 20, 20, 20, kind="activity_group")
        deck_back["owner_activity_id"] = "deck_frame"
        trump["owner_activity_id"] = "deck_frame"

        _, overlaps = detect_geometry_issues(
            [deck_back, trump],
            self.screen_size,
            collision_subject_keys=(deck_back["key"], trump["key"]),
        )

        self.assertEqual(overlaps, [])

    def test_frame_and_its_child_group_can_overlap(self):
        frame = make_object("frame:deck_frame", 20, 20, 20, 20, object_id="deck_frame")
        card_back = make_object("activity_group:deck_frame.card_back", 20, 20, 20, 20, kind="activity_group")
        card_back["owner_frame_id"] = "deck_frame"
        card_back["owner_activity_id"] = "deck_frame"

        _, overlaps = detect_geometry_issues(
            [frame, card_back],
            self.screen_size,
            collision_subject_keys=(frame["key"], card_back["key"]),
        )

        self.assertEqual(overlaps, [])

    def test_collect_objects_includes_bottom_player_fan_from_nested_activity(self):
        screen = build_screen()
        self.addCleanup(__import__("pygame").quit)

        object_keys = {item["key"] for item in collect_objects(screen)}

        self.assertIn("fan_occupied:bottom_player_hand", object_keys)

    def test_prepare_collision_test_state_creates_all_four_filled_fans(self):
        screen = build_screen()
        self.addCleanup(__import__("pygame").quit)

        prepare_collision_test_state(screen)
        object_keys = {item["key"] for item in collect_objects(screen)}

        self.assertEqual(
            {
                "fan_occupied:left_player_hand",
                "fan_occupied:right_player_hand",
                "fan_occupied:top_player_hand",
                "fan_occupied:bottom_player_hand",
            } - object_keys,
            set(),
        )

    def test_build_screen_enables_bottom_player_fan_debug_overlay(self):
        screen = build_screen()
        self.addCleanup(__import__("pygame").quit)

        activity = screen.get_named_activity("bottom_player_hand")
        visible_cards_activity = getattr(activity, "hand_activity", None)
        player_hand_activity = getattr(visible_cards_activity, "hand_activity", None)

        self.assertIsNotNone(player_hand_activity)
        self.assertTrue(getattr(player_hand_activity, "debug_fan_rect", False))

    def test_current_bottom_left_slot_has_no_geometry_issues(self):
        screen = build_screen()
        self.addCleanup(__import__("pygame").quit)

        report = detect_geometry_issues(
            collect_objects(screen),
            screen.SCREEN_SIZE,
            collision_subject_keys=("frame:cards_slot_frame_8",),
        )

        self.assertEqual(report, ([], []))

    def test_existing_table_slots_keep_fixed_legacy_rects(self):
        screen = build_screen()
        self.addCleanup(__import__("pygame").quit)

        objects = {
            item["key"]: item["rect"]
            for item in collect_objects(screen)
            if item["key"].startswith("frame:cards_slot_frame")
        }

        self.assertEqual(objects["frame:cards_slot_frame"], {"x": 567, "y": 292, "width": 138, "height": 136, "left": 567, "top": 292, "right": 705, "bottom": 428, "center": [636, 360]})
        self.assertEqual(objects["frame:cards_slot_frame_2"], {"x": 424, "y": 292, "width": 138, "height": 136, "left": 424, "top": 292, "right": 562, "bottom": 428, "center": [493, 360]})
        self.assertEqual(objects["frame:cards_slot_frame_3"], {"x": 710, "y": 292, "width": 138, "height": 136, "left": 710, "top": 292, "right": 848, "bottom": 428, "center": [779, 360]})
        self.assertEqual(objects["frame:cards_slot_frame_4"], {"x": 281, "y": 292, "width": 138, "height": 136, "left": 281, "top": 292, "right": 419, "bottom": 428, "center": [350, 360]})
        self.assertEqual(objects["frame:cards_slot_frame_5"], {"x": 853, "y": 292, "width": 138, "height": 136, "left": 853, "top": 292, "right": 991, "bottom": 428, "center": [922, 360]})
        self.assertEqual(objects["frame:cards_slot_frame_6"], {"x": 281, "y": 144, "width": 138, "height": 136, "left": 281, "top": 144, "right": 419, "bottom": 280, "center": [350, 212]})
        self.assertEqual(objects["frame:cards_slot_frame_7"], {"x": 853, "y": 144, "width": 138, "height": 136, "left": 853, "top": 144, "right": 991, "bottom": 280, "center": [922, 212]})

    def test_upper_left_slot_override_does_not_expand_bottom_hand_corridor(self):
        screen = build_screen()
        self.addCleanup(__import__("pygame").quit)

        bottom_fan = next(
            item for item in collect_objects(screen)
            if item["key"] == "fan_occupied:bottom_player_hand"
        )

        self.assertGreaterEqual(bottom_fan["rect"]["left"], 300)

    def test_bottom_player_hand_keeps_legacy_interactive_fan_geometry(self):
        screen = build_screen()
        self.addCleanup(__import__("pygame").quit)

        bottom_fan = next(
            item["rect"]
            for item in collect_objects(screen)
            if item["key"] == "fan_occupied:bottom_player_hand"
        )

        self.assertEqual(
            bottom_fan,
            {
                "x": 336,
                "y": 439,
                "width": 608,
                "height": 256,
                "left": 336,
                "top": 439,
                "right": 944,
                "bottom": 695,
                "center": [640, 567],
            },
        )

    def test_slot_override_does_not_change_any_hand_fan_rect(self):
        screen = build_screen()
        self.addCleanup(__import__("pygame").quit)

        before = {
            item["key"]: item["rect"]
            for item in collect_objects(screen)
            if item["key"].startswith("fan_occupied:")
        }

        screen.apply_gui_fixture_tree(
            {
                "play_area_frame": {
                    "activity": {
                        "slot_local_rects": {
                            "cards_slot_frame_8": [20, 20, 138, 136],
                        },
                    },
                },
            }
        )
        screen.update(0.0)

        after = {
            item["key"]: item["rect"]
            for item in collect_objects(screen)
            if item["key"].startswith("fan_occupied:")
        }

        self.assertEqual(after, before)

    def test_bottom_hand_signature_ignores_extra_slot_frame(self):
        screen = build_screen()
        self.addCleanup(__import__("pygame").quit)

        before_signature = screen.get_bottom_player_hand_fan_area_signature()

        screen.apply_gui_fixture_tree(
            {
                "play_area_frame": {
                    "activity": {
                        "slot_local_rects": {
                            "cards_slot_frame_8": [20, 20, 138, 136],
                        },
                    },
                },
            }
        )
        screen.update(0.0)

        self.assertEqual(
            screen.get_bottom_player_hand_fan_area_signature(),
            before_signature,
        )

    def test_bottom_hand_signature_changes_when_anchor_slot_moves(self):
        screen = build_screen()
        self.addCleanup(__import__("pygame").quit)

        before_signature = screen.get_bottom_player_hand_fan_area_signature()

        screen.apply_gui_fixture_tree(
            {
                "play_area_frame": {
                    "activity": {
                        "slot_local_rects": {
                            "cards_slot_frame_4": [220, 272, 138, 136],
                        },
                    },
                },
            }
        )
        screen.update(0.0)

        self.assertNotEqual(
            screen.get_bottom_player_hand_fan_area_signature(),
            before_signature,
        )

    def test_hand_card_count_changes_do_not_move_play_area_slots(self):
        screen = build_screen()
        self.addCleanup(__import__("pygame").quit)

        before = {
            item["key"]: item["rect"]
            for item in collect_objects(screen)
            if item["key"].startswith("frame:cards_slot_frame")
        }

        screen.apply_card_counts_fixture(
            {
                "left_player_hand": 3,
                "right_player_hand": 14,
                "top_player_hand": 2,
                "bottom_player_hand": 11,
            }
        )
        screen.update(0.0)

        after = {
            item["key"]: item["rect"]
            for item in collect_objects(screen)
            if item["key"].startswith("frame:cards_slot_frame")
        }

        self.assertEqual(after, before)
