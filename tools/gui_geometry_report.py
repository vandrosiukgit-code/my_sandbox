"""Capture a TableScreen GUI geometry snapshot for layout review."""

from __future__ import annotations

import argparse
import json
import os
import sys

import pygame

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from core import GameController
from core.resource import ResourceManager
from group import GroupStore
from screens.table_screen import TableScreen


ASSETS_DIR = os.path.join(PROJECT_DIR, "assets")
DEFAULT_COLLISION_TEST_CARD_COUNTS = {
    "left_player_hand": 18,
    "right_player_hand": 18,
    "top_player_hand": 18,
    "bottom_player_hand": 18,
}


def rect_data(rect):
    return {
        "x": rect.x,
        "y": rect.y,
        "width": rect.width,
        "height": rect.height,
        "left": rect.left,
        "top": rect.top,
        "right": rect.right,
        "bottom": rect.bottom,
        "center": [rect.centerx, rect.centery],
    }


def build_screen():
    pygame.init()
    pygame.display.set_mode(TableScreen.SCREEN_SIZE, flags=getattr(pygame, "HIDDEN", 0))
    ResourceManager.build_runtime_cache(ASSETS_DIR)
    group_store = GroupStore(resource_manager=ResourceManager)
    group_store.build()
    game_controller = GameController(GameController.create_fixture_state())
    screen = TableScreen(group_store=group_store, game_controller=game_controller)
    screen.update(0.0)
    prepare_collision_test_state(screen)
    return screen


def prepare_collision_test_state(screen, card_counts=None):
    counts = dict(DEFAULT_COLLISION_TEST_CARD_COUNTS)
    if card_counts:
        counts.update(card_counts)
    applier = getattr(screen, "apply_card_counts_fixture", None)
    if callable(applier):
        applier(counts)
    screen.update(0.0)
    return screen


def collect_objects(screen):
    objects = []
    for frame in screen.iter_screen_frames():
        objects.append(
            make_object(
                key=f"frame:{frame.id}",
                kind="frame",
                object_id=frame.id,
                owner_frame_id=getattr(getattr(frame, "parent_frame", None), "id", None),
                rect=frame.rect,
                hit_rect=frame.hit_rect,
            )
        )

    generated_owner_ids = {}
    for activity_id, activity in screen.iter_named_activities():
        if not hasattr(activity, "iter_generated_groups"):
            continue
        for group in activity.iter_generated_groups():
            generated_owner_ids[group.id] = activity_id

    seen_group_ids = set()
    for group in screen.iter_active_groups():
        objects.append(make_group_object(group, "configured_group", None))
        seen_group_ids.add(group.id)
    for group in screen.iter_activity_generated_groups():
        if group.id in seen_group_ids:
            continue
        objects.append(
            make_group_object(
                group,
                "activity_group",
                generated_owner_ids.get(group.id),
            )
        )
        seen_group_ids.add(group.id)

    for activity_id, activity in screen.iter_named_activities():
        nested_activity = find_nested_activity_with_method(
            activity,
            "get_fan_occupied_screen_rect",
        )
        if nested_activity is None:
            continue
        rect = nested_activity.get_fan_occupied_screen_rect()
        if rect is not None:
            objects.append(
                make_object(
                    key=f"fan_occupied:{activity_id}",
                    kind="fan_occupied",
                    object_id=activity_id,
                    owner_frame_id=None,
                    rect=rect,
                    hit_rect=rect,
                )
            )
    return objects


def find_nested_activity_with_method(activity, method_name):
    while activity is not None:
        if callable(getattr(activity, method_name, None)):
            return activity
        activity = getattr(activity, "hand_activity", None)
    return None


def make_group_object(group, kind, owner_activity_id):
    owner_frame = getattr(group, "parent_frame", None)
    return make_object(
        key=f"{kind}:{group.id}",
        kind=kind,
        object_id=group.id,
        owner_frame_id=getattr(owner_frame, "id", None),
        owner_activity_id=owner_activity_id,
        rect=group.rect,
        hit_rect=group.hit_rect,
    )


def make_object(key, kind, object_id, owner_frame_id, rect, hit_rect, owner_activity_id=None):
    return {
        "key": key,
        "kind": kind,
        "id": object_id,
        "owner_frame_id": owner_frame_id,
        "owner_activity_id": owner_activity_id,
        "rect": rect_data(rect),
        "hit_rect": rect_data(hit_rect),
    }


def detect_geometry_issues(
    objects,
    screen_size,
    collision_subject_keys=None,
    ignored_collision_keys=(),
    ignored_collision_pairs=(),
):
    """Return P0/P1 layout violations with their exact geometry parameters.

    ``collision_subject_keys`` identifies objects being placed in this test
    session.  When it is omitted, table slots and the deck frame are checked.
    ``ignored_collision_keys`` and ``ignored_collision_pairs`` are a
    session-local allowlist; they never alter runtime layout rules.
    """
    screen_rect = pygame.Rect(0, 0, *screen_size)
    subject_keys = set(collision_subject_keys or default_collision_subject_keys(objects))
    ignored_keys = set(ignored_collision_keys)
    ignored_pairs = {normalise_pair(pair) for pair in ignored_collision_pairs}
    subjects = [item for item in objects if item["key"] in subject_keys]
    outside_screen = []
    for item in subjects:
        rect = to_rect(item["rect"])
        visible_rect = rect.clip(screen_rect)
        outside_area = rect.width * rect.height - visible_rect.width * visible_rect.height
        if outside_area > 0:
            outside_screen.append(
                {
                    "severity": "P0",
                    "key": item["key"],
                    "rect": rect_data(rect),
                    "screen_rect": rect_data(screen_rect),
                    "visible_rect": rect_data(visible_rect),
                    "outside_area": outside_area,
                }
            )

    protected_zones = [item for item in objects if is_protected_zone(item)]
    overlaps = []
    reported_pairs = set()
    for first in subjects:
        first_rect = to_rect(first["rect"])
        for second in protected_zones:
            pair = normalise_pair((first["key"], second["key"]))
            if first["key"] == second["key"] or pair in reported_pairs:
                continue
            reported_pairs.add(pair)
            if (
                first.get("owner_frame_id") == second["id"]
                or second.get("owner_frame_id") == first["id"]
            ):
                continue
            if first.get("owner_activity_id") and first.get("owner_activity_id") == second.get("owner_activity_id"):
                continue
            if first["key"] in ignored_keys or second["key"] in ignored_keys or pair in ignored_pairs:
                continue
            intersection = first_rect.clip(to_rect(second["rect"]))
            if intersection.width <= 0 or intersection.height <= 0:
                continue
            overlaps.append(
                {
                    "first_key": first["key"],
                    "second_key": second["key"],
                    "intersection": rect_data(intersection),
                    "area": intersection.width * intersection.height,
                    "severity": "P1",
                }
            )
    return outside_screen, overlaps


def default_collision_subject_keys(objects):
    return [item["key"] for item in objects if is_layout_subject(item)]


def is_layout_subject(item):
    if item["kind"] == "activity_group" and item["owner_activity_id"] == "deck_frame":
        return True
    return item["kind"] == "frame" and (
        item["id"] == "deck_frame" or item["id"].startswith("cards_slot_frame")
    )


def is_protected_zone(item):
    return (
        is_layout_subject(item)
        or item["kind"] == "fan_occupied"
        or (item["kind"] == "frame" and item["id"].endswith("_portrait"))
    )


def normalise_pair(pair):
    return tuple(sorted(pair))


def to_rect(data):
    return pygame.Rect(data["x"], data["y"], data["width"], data["height"])


def apply_candidate_rects(objects, candidate_rects):
    """Return a snapshot with temporary screen-space candidate rects applied."""
    candidates = candidate_rects or {}
    available_keys = {item["key"] for item in objects}
    unknown_keys = set(candidates) - available_keys
    if unknown_keys:
        raise ValueError(f"Unknown geometry candidate keys: {sorted(unknown_keys)}")

    updated_objects = []
    for item in objects:
        updated_item = dict(item)
        if item["key"] in candidates:
            x, y, width, height = candidates[item["key"]]
            candidate_rect = pygame.Rect(x, y, width, height)
            updated_item["rect"] = rect_data(candidate_rect)
            updated_item["hit_rect"] = rect_data(candidate_rect)
        updated_objects.append(updated_item)
    return updated_objects


def build_report(
    screen,
    collision_subject_keys=None,
    ignored_collision_keys=(),
    ignored_collision_pairs=(),
    candidate_rects=None,
):
    objects = apply_candidate_rects(collect_objects(screen), candidate_rects)
    outside_screen, overlaps = detect_geometry_issues(
        objects,
        TableScreen.SCREEN_SIZE,
        collision_subject_keys=collision_subject_keys,
        ignored_collision_keys=ignored_collision_keys,
        ignored_collision_pairs=ignored_collision_pairs,
    )
    return {
        "screen": {"width": TableScreen.SCREEN_SIZE[0], "height": TableScreen.SCREEN_SIZE[1]},
        "objects": objects,
        "collision_subject_keys": collision_subject_keys or default_collision_subject_keys(objects),
        "candidate_rects": {
            key: rect_data(pygame.Rect(*rect)) for key, rect in (candidate_rects or {}).items()
        },
        "ignored_collision_keys": list(ignored_collision_keys),
        "ignored_collision_pairs": [list(pair) for pair in ignored_collision_pairs],
        "outside_screen": outside_screen,
        "overlaps": overlaps,
        "violations": [*outside_screen, *overlaps],
    }


def assert_no_geometry_issues(report):
    """Raise AssertionError with the full P0/P1 payload for test runners."""
    if report["violations"]:
        raise AssertionError(json.dumps(report["violations"], ensure_ascii=False, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", help="Write the JSON report to this path.")
    parser.add_argument(
        "--collision-subject",
        action="append",
        dest="collision_subject_keys",
        help="Object key to validate; repeat for multiple objects.",
    )
    parser.add_argument(
        "--ignore-collision-object",
        action="append",
        default=[],
        dest="ignored_collision_keys",
        help="Ignore collisions involving this object key for this invocation.",
    )
    parser.add_argument(
        "--ignore-collision-pair",
        action="append",
        nargs=2,
        default=[],
        metavar=("FIRST_KEY", "SECOND_KEY"),
        dest="ignored_collision_pairs",
        help="Ignore only this object pair for this invocation.",
    )
    parser.add_argument(
        "--candidate-rect",
        action="append",
        nargs=5,
        default=[],
        metavar=("OBJECT_KEY", "X", "Y", "WIDTH", "HEIGHT"),
        help="Temporarily test this object rect without changing the GUI scene.",
    )
    args = parser.parse_args(argv)
    candidate_rects = {
        key: tuple(int(value) for value in values)
        for key, *values in args.candidate_rect
    }
    try:
        report = build_report(
            build_screen(),
            collision_subject_keys=args.collision_subject_keys,
            ignored_collision_keys=args.ignored_collision_keys,
            ignored_collision_pairs=args.ignored_collision_pairs,
            candidate_rects=candidate_rects,
        )
        payload = json.dumps(report, ensure_ascii=False, indent=2)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as output_file:
                output_file.write(payload)
                output_file.write("\n")
        else:
            print(payload)
    finally:
        pygame.quit()
    return 1 if report["violations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
