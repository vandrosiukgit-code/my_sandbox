"""Durable source of configured group placement inside screen frame hierarchies."""

from __future__ import annotations

import copy
import json
import os


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
SCREEN_LAYOUT_PATH = os.path.join(PROJECT_DIR, "assets", "screen_layout.json")


DEFAULT_SCREEN_LAYOUT = {
    "screens": {
        "table_screen": {
            "root_frame_id": "game_table",
            "size": [1280, 720],
            "frames": {
                "game_table": {
                    "frame_id": "game_table",
                    "parent_frame_id": None,
                    "rect": [0, 0, 1280, 720],
                }
            },
            "groups": {
                "table_group": {"frame_id": "game_table", "position": [0, 0]},
                "left_player": {"frame_id": "left_player_portrait", "position": [0, 0]},
                "right_player": {"frame_id": "right_player_portrait", "position": [0, 0]},
                "top_player": {"frame_id": "top_player_portrait", "position": [0, 0]},
                "bottom_player": {"frame_id": "bottom_player_portrait", "position": [0, 0]},
                "take_btn": {"frame_id": "game_table", "position": [980, 500]},
            }
        }
    }
}


def get_screen_layout_path():
    return SCREEN_LAYOUT_PATH


def empty_screen_layout():
    return {"screens": {}}


def load_screen_layout():
    if not os.path.exists(SCREEN_LAYOUT_PATH):
        return copy.deepcopy(DEFAULT_SCREEN_LAYOUT)
    with open(SCREEN_LAYOUT_PATH, "r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        return copy.deepcopy(DEFAULT_SCREEN_LAYOUT)
    screens = payload.get("screens")
    if not isinstance(screens, dict):
        payload["screens"] = {}
    return payload


def save_screen_layout(payload):
    os.makedirs(os.path.dirname(SCREEN_LAYOUT_PATH), exist_ok=True)
    with open(SCREEN_LAYOUT_PATH, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")
    return payload


def get_screen_group_placements(screen_id, payload=None):
    payload = copy.deepcopy(payload) if payload is not None else load_screen_layout()
    screen_payload = payload.get("screens", {}).get(screen_id, {})
    placements = screen_payload.get("groups", {})
    return placements if isinstance(placements, dict) else {}


def find_group_placement(group_id, payload=None):
    payload = payload or load_screen_layout()
    for screen_id, screen_payload in payload.get("screens", {}).items():
        groups = screen_payload.get("groups", {})
        if isinstance(groups, dict) and group_id in groups:
            placement = groups[group_id]
            if isinstance(placement, dict):
                return screen_id, placement
    return None, None


def upsert_group_placement(group_id, screen_id, frame_id, position=(0, 0), payload=None):
    payload = copy.deepcopy(payload) if payload is not None else load_screen_layout()
    screens = payload.setdefault("screens", {})
    screen_payload = screens.setdefault(screen_id, {})
    groups = screen_payload.setdefault("groups", {})
    groups[group_id] = {
        "frame_id": str(frame_id),
        "position": [int(position[0]), int(position[1])],
    }
    return payload


def upsert_screen(screen_id, root_frame_id, size, payload=None):
    payload = copy.deepcopy(payload) if payload is not None else load_screen_layout()
    screens = payload.setdefault("screens", {})
    width = int(size[0])
    height = int(size[1])
    screens[str(screen_id)] = {
        "root_frame_id": str(root_frame_id),
        "size": [width, height],
        "frames": {
            str(root_frame_id): {
                "frame_id": str(root_frame_id),
                "parent_frame_id": None,
                "rect": [0, 0, width, height],
            }
        },
        "groups": screens.get(str(screen_id), {}).get("groups", {}),
    }
    return payload


def upsert_frame(screen_id, frame_id, parent_frame_id, rect, payload=None):
    payload = copy.deepcopy(payload) if payload is not None else load_screen_layout()
    screens = payload.setdefault("screens", {})
    screen_payload = screens.setdefault(str(screen_id), {})
    frames = screen_payload.setdefault("frames", {})
    frames[str(frame_id)] = {
        "frame_id": str(frame_id),
        "parent_frame_id": str(parent_frame_id) if parent_frame_id is not None else None,
        "rect": [int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])],
    }
    screen_payload.setdefault("groups", {})
    return payload
