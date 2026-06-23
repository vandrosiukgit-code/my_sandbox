"""Automated contracts for P0/P1 GUI layout diagnostics."""

import unittest

from tools.gui_geometry_report import apply_candidate_rects, detect_geometry_issues


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
