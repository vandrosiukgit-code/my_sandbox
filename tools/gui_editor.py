"""PySide6 GUI editor for GameScreen / Frame / Group data."""

from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
import json
import os
import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QBrush, QColor, QCursor, QFont, QPixmap
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QInputDialog,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStyle,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

import group_config  # noqa: E402
import screen_layout_config  # noqa: E402
from core.resource import ResourceManager  # noqa: E402


ASSETS_DIR = os.path.join(PROJECT_DIR, "assets")
RESOURCE_MANIFEST_PATH = os.path.join(ASSETS_DIR, "resource_manifest.json")
GUI_EDITOR_ASSETS_DIR = os.path.join(PROJECT_DIR, "tools", "gui_editor_assets")
GUI_EDITOR_SETTINGS_PATH = os.path.join(PROJECT_DIR, "tools", "gui_editor_settings.json")


@dataclass(frozen=True)
class GuiExplorerNode:
    node_id: str
    kind: str
    label: str
    parent_id: str | None = None
    payload: dict | None = None


def _load_preview_fixture_json(fixture_name):
    fixture_path = os.path.join(PROJECT_DIR, "fixtures", fixture_name)
    with open(fixture_path, "r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def build_table_screen_gui_preview_state():
    base_fixture = _load_preview_fixture_json("table_screen_fixture.json")
    discard_fixture = _load_preview_fixture_json("discard_table_fixture.json")
    start_game_fixture = base_fixture.get("activities", {}).get("start_game", {})
    return {
        "bot_hand_counts": {
            "left_player_hand": 6,
            "right_player_hand": 6,
            "top_player_hand": 6,
        },
        "bottom_player_cards": tuple(start_game_fixture.get("bottom_player_card_resource_keys", ())[:6]),
        "table_slots": {
            slot_id: tuple(cards)
            for slot_id, cards in discard_fixture.get("table_slots", {}).items()
        },
        "trump_resource_key": base_fixture.get("activities", {}).get("deck_frame", {}).get("trump_resource_key", "cards.a_of_spades"),
    }


def prepare_static_preview_screen(screen):
    for frame in screen.screen_frames.values():
        frame.actions = []
    if hasattr(screen, "clear_play_area_slot_cards"):
        screen.clear_play_area_slot_cards()
    screen.update(0.0)


def run_table_screen_gui_preview():
    from core import GameController
    from core.render_engine import RenderEngine
    from group import GroupStore
    from screens.table_screen import TableScreen

    game_controller = GameController(GameController.create_fixture_state())
    group_store = GroupStore(resource_manager=ResourceManager)
    preview_state = build_table_screen_gui_preview_state()

    def screen_factory(_render_context=None):
        ResourceManager.build_runtime_cache(ASSETS_DIR)
        group_store.build()
        screen = TableScreen(group_store=group_store, game_controller=game_controller)
        prepare_static_preview_screen(screen)
        screen.controller_game_started = True
        screen.controller_owned_visual_state = False
        for activity_id, card_count in preview_state["bot_hand_counts"].items():
            activity = screen.get_named_activity(activity_id)
            if activity is not None:
                activity.apply_fixture({"card_count": card_count})
        bottom_hand = screen.get_named_activity("bottom_player_hand")
        if bottom_hand is not None:
            bottom_hand.apply_fixture({"cards": preview_state["bottom_player_cards"]})
        deck_activity = screen.get_named_activity("deck_frame")
        if deck_activity is not None:
            deck_activity.apply_fixture({"trump_resource_key": preview_state["trump_resource_key"]})
        for slot_id, cards in preview_state["table_slots"].items():
            slot_activity = screen.get_named_activity(slot_id)
            if slot_activity is not None:
                slot_activity.apply_fixture({"cards": cards, "card_visual_state": "visible"})
        screen.update(0.0)
        return screen

    render_engine = RenderEngine(
        screen_factory=screen_factory,
        screen_size=TableScreen.SCREEN_SIZE,
        title="The Fool's Reef - screen: table_screen [gui preview]",
    )
    render_engine.run()
    return 0


def run_layout_screen_preview(screen_id):
    from core.render_engine import RenderEngine
    from game_screen.game_screen import GameScreen
    from group import GroupStore

    layout = screen_layout_config.load_screen_layout()
    screen_payload = layout.get("screens", {}).get(screen_id)
    if not isinstance(screen_payload, dict):
        print(f"Unknown screen: {screen_id}")
        return 2

    frames_payload = screen_payload.get("frames", {})
    if not isinstance(frames_payload, dict) or not frames_payload:
        print(f"Screen has no frame layout for preview: {screen_id}")
        return 2

    class LayoutPreviewScreen(GameScreen):
        def __init__(self, group_store, background_color=(30, 30, 30)):
            super().__init__(group_store=group_store, game_controller=None, background_color=background_color)
            self.screen_payload = copy.deepcopy(screen_payload)
            self._build_layout_tree()
            self._place_groups()

        def _build_layout_tree(self):
            pending = dict(self.screen_payload.get("frames", {}))
            while pending:
                progress = False
                for frame_id, frame_spec in list(pending.items()):
                    if not isinstance(frame_spec, dict):
                        pending.pop(frame_id)
                        progress = True
                        continue
                    parent_frame_id = frame_spec.get("parent_frame_id")
                    if parent_frame_id and not self.has_screen_frame(parent_frame_id):
                        continue
                    self.create_frame(
                        frame_id,
                        rect=frame_spec.get("rect", (0, 0, 0, 0)),
                        parent_frame_id=parent_frame_id,
                    )
                    pending.pop(frame_id)
                    progress = True
                if progress:
                    continue
                unresolved = ", ".join(sorted(pending))
                raise RuntimeError(f"Cannot resolve frame hierarchy for preview screen {screen_id}: {unresolved}")

        def _place_groups(self):
            groups = self.screen_payload.get("groups", {})
            if not isinstance(groups, dict):
                return
            for group_id, placement in groups.items():
                if not isinstance(placement, dict):
                    continue
                frame_id = placement.get("frame_id")
                if not frame_id or not self.has_screen_frame(frame_id):
                    continue
                if self.group_store is None or not self.group_store.has(group_id):
                    continue
                self.activate_group(group_id)
                self.put_group_in_frame(group_id, frame_id, position=placement.get("position", (0, 0)))

    group_store = GroupStore(resource_manager=ResourceManager)
    screen_size = tuple(screen_payload.get("size", (1280, 720)))
    if len(screen_size) != 2:
        screen_size = (1280, 720)

    def screen_factory(_render_context=None):
        ResourceManager.build_runtime_cache(ASSETS_DIR)
        group_store.build()
        return LayoutPreviewScreen(group_store=group_store)

    render_engine = RenderEngine(
        screen_factory=screen_factory,
        screen_size=screen_size,
        title=f"The Fool's Reef - screen: {screen_id}",
    )
    render_engine.run()
    return 0


class GuiEditorDataService:
    """Adapter that builds explorer trees and updates RM manifest entries."""

    def __init__(self, project_dir=PROJECT_DIR):
        self.project_dir = os.path.abspath(project_dir)
        self.assets_dir = os.path.join(self.project_dir, "assets")

    def load_resource_manifest(self):
        manifest_path = self.resource_manifest_path
        if not os.path.exists(manifest_path):
            return {"resources": {}, "folders": []}
        with open(manifest_path, "r", encoding="utf-8") as file:
            payload = json.load(file)
        if not isinstance(payload, dict):
            return {"resources": {}, "folders": []}
        resources = payload.get("resources")
        if not isinstance(resources, dict):
            payload["resources"] = {}
        folders = payload.get("folders")
        if not isinstance(folders, list):
            payload["folders"] = []
        payload["folders"] = self.normalize_folder_list(payload["folders"])
        return payload

    @property
    def resource_manifest_path(self):
        return os.path.join(self.assets_dir, "resource_manifest.json")

    def save_resource_manifest(self, manifest):
        normalized_resources = ResourceManager.normalize_manifest(manifest)
        normalized = {
            "resources": normalized_resources.get("resources", {}),
            "folders": self.normalize_folder_list(manifest.get("folders", [])),
        }
        os.makedirs(os.path.dirname(self.resource_manifest_path), exist_ok=True)
        with open(self.resource_manifest_path, "w", encoding="utf-8") as file:
            json.dump(normalized, file, ensure_ascii=False, indent=2)
            file.write("\n")
        return normalized

    def load_editor_settings(self):
        if not os.path.exists(GUI_EDITOR_SETTINGS_PATH):
            return {}
        with open(GUI_EDITOR_SETTINGS_PATH, "r", encoding="utf-8") as file:
            payload = json.load(file)
        return payload if isinstance(payload, dict) else {}

    def save_editor_settings(self, settings):
        with open(GUI_EDITOR_SETTINGS_PATH, "w", encoding="utf-8") as file:
            json.dump(settings, file, ensure_ascii=False, indent=2)
            file.write("\n")
        return settings

    def get_default_add_png_dir(self):
        settings = self.load_editor_settings()
        path = settings.get("default_add_png_dir")
        if not isinstance(path, str) or not path.strip():
            return None
        return path

    def set_default_add_png_dir(self, directory_path):
        settings = self.load_editor_settings()
        settings["default_add_png_dir"] = os.path.abspath(directory_path)
        self.save_editor_settings(settings)
        return settings["default_add_png_dir"]

    def suggest_manifest_path(self, file_path):
        absolute_path = os.path.abspath(file_path)
        assets_root = os.path.abspath(self.assets_dir)
        if not absolute_path.lower().endswith(".png"):
            raise ValueError("Only .png files are supported")
        try:
            relative_path = os.path.relpath(absolute_path, assets_root)
        except ValueError as error:
            raise ValueError("PNG must be inside assets/") from error
        if relative_path.startswith(".."):
            raise ValueError("PNG must be inside assets/")
        return ResourceManager.normalize_manifest_path(relative_path)

    def add_png_to_manifest(self, file_path, manifest_path=None):
        absolute_path = os.path.abspath(file_path)
        assets_root = os.path.abspath(self.assets_dir)
        suggested_path = self.suggest_manifest_path(absolute_path)
        manifest_path = ResourceManager.normalize_manifest_path((manifest_path or suggested_path).strip())
        if not manifest_path or not manifest_path.lower().endswith(".png"):
            raise ValueError("Manifest path must point to a .png file")
        if manifest_path.startswith("../") or "/../" in f"/{manifest_path}":
            raise ValueError("Manifest path must stay inside assets/")

        entry = ResourceManager.create_default_manifest_entry(absolute_path, assets_root)
        resource_key = ResourceManager.build_resource_key(manifest_path)
        manifest = self.load_resource_manifest()
        resources = manifest.setdefault("resources", {})
        manifest.setdefault("folders", [])
        resources[resource_key] = entry
        saved_manifest = self.save_resource_manifest(manifest)
        return resource_key, saved_manifest["resources"][resource_key]

    def remove_png_from_manifest(self, resource_key):
        manifest = self.load_resource_manifest()
        resources = manifest.setdefault("resources", {})
        if resource_key not in resources:
            return None
        removed_entry = resources.pop(resource_key)
        self.save_resource_manifest(manifest)
        return removed_entry

    def rename_manifest_resource(self, resource_key, new_name):
        source = self.normalize_folder_path(resource_key)
        target_name = self.normalize_folder_path(new_name).split(".")[-1]
        prefix, _separator, _tail = source.rpartition(".")
        target = f"{prefix}.{target_name}" if prefix else target_name
        if target == source:
            return target

        manifest = self.load_resource_manifest()
        resources = manifest.setdefault("resources", {})
        folders = manifest.setdefault("folders", [])
        if source not in resources:
            raise ValueError(f"Manifest entry not found: {source}")
        if target in resources or target in folders:
            raise ValueError(f"Manifest entry already exists: {target}")
        resources[target] = resources.pop(source)
        self.save_resource_manifest(manifest)
        return target

    @staticmethod
    def normalize_folder_list(folders):
        normalized = []
        seen = set()
        for folder_path in folders:
            candidate = GuiEditorDataService.normalize_folder_path(folder_path)
            if not candidate or candidate in seen:
                continue
            normalized.append(candidate)
            seen.add(candidate)
        return sorted(normalized)

    @staticmethod
    def normalize_folder_path(folder_path):
        if not isinstance(folder_path, str):
            raise ValueError("Folder path must be a string")
        candidate = folder_path.strip().replace("/", ".")
        candidate = ".".join(part for part in candidate.split(".") if part)
        if not candidate:
            raise ValueError("Folder name is required")
        if candidate.startswith(".") or candidate.endswith(".") or ".." in candidate:
            raise ValueError("Folder path is invalid")
        return candidate

    def create_manifest_folder(self, folder_path):
        manifest = self.load_resource_manifest()
        folders = set(manifest.setdefault("folders", []))
        normalized = self.normalize_folder_path(folder_path)
        parts = normalized.split(".")
        for index in range(len(parts)):
            folders.add(".".join(parts[: index + 1]))
        manifest["folders"] = sorted(folders)
        saved = self.save_resource_manifest(manifest)
        return normalized, saved["folders"]

    def rename_manifest_folder(self, folder_path, new_name):
        source = self.normalize_folder_path(folder_path)
        target_name = self.normalize_folder_path(new_name).split(".")[-1]
        prefix, _separator, _tail = source.rpartition(".")
        target = f"{prefix}.{target_name}" if prefix else target_name
        if target == source:
            return target

        manifest = self.load_resource_manifest()
        folders = manifest.setdefault("folders", [])
        resources = manifest.setdefault("resources", {})
        if target in folders or any(key == target or key.startswith(f"{target}.") for key in resources):
            raise ValueError(f"Folder already exists: {target}")
        manifest["folders"] = self._rename_folder_paths(folders, source, target)
        manifest["resources"] = self._rename_resource_keys(resources, source, target)
        self.save_resource_manifest(manifest)
        return target

    def move_manifest_nodes(self, node_ids, target_folder):
        target = self.normalize_folder_path(target_folder)
        manifest = self.load_resource_manifest()
        folders = manifest.setdefault("folders", [])
        resources = manifest.setdefault("resources", {})
        folder_set = set(folders)
        if target not in folder_set and target not in self._implicit_folder_paths(resources):
            raise ValueError(f"Unknown target folder: {target}")

        updated_resources = dict(resources)
        updated_folders = list(folders)
        for node_id in sorted(set(node_ids), key=lambda value: (value.count("."), value)):
            normalized = self.normalize_folder_path(node_id)
            if normalized == target or target.startswith(f"{normalized}."):
                raise ValueError("Cannot move a folder into itself")
            basename = normalized.split(".")[-1]
            destination = f"{target}.{basename}"
            if normalized in folder_set:
                updated_folders = self._rename_folder_paths(updated_folders, normalized, destination)
                updated_resources = self._rename_resource_keys(updated_resources, normalized, destination)
                folder_set = set(updated_folders)
            elif normalized in updated_resources:
                if destination in updated_resources:
                    raise ValueError(f"Resource already exists: {destination}")
                updated_resources[destination] = updated_resources.pop(normalized)
            else:
                raise ValueError(f"Unknown manifest node: {normalized}")

        manifest["folders"] = updated_folders
        manifest["resources"] = updated_resources
        self.save_resource_manifest(manifest)
        return target

    def remove_manifest_folder(self, folder_path):
        target = self.normalize_folder_path(folder_path)
        manifest = self.load_resource_manifest()
        folders = manifest.setdefault("folders", [])
        resources = manifest.setdefault("resources", {})
        had_folder = target in folders
        had_resources = any(key.startswith(f"{target}.") for key in resources)
        if not had_folder and not had_resources:
            return None

        manifest["folders"] = [
            folder for folder in folders
            if folder != target and not folder.startswith(f"{target}.")
        ]
        manifest["resources"] = {
            resource_key: entry
            for resource_key, entry in resources.items()
            if not resource_key.startswith(f"{target}.")
        }
        self.save_resource_manifest(manifest)
        return target

    @staticmethod
    def _rename_folder_paths(folders, source, target):
        updated = []
        for folder in folders:
            if folder == source or folder.startswith(f"{source}."):
                updated.append(target + folder[len(source) :])
            else:
                updated.append(folder)
        return GuiEditorDataService.normalize_folder_list(updated)

    @staticmethod
    def _rename_resource_keys(resources, source, target):
        updated = {}
        for resource_key, entry in resources.items():
            if resource_key == source or resource_key.startswith(f"{source}."):
                updated[target + resource_key[len(source) :]] = entry
            else:
                updated[resource_key] = entry
        return updated

    @staticmethod
    def _implicit_folder_paths(resources):
        folders = set()
        for resource_key in resources:
            parts = str(resource_key).split(".")
            for index in range(len(parts) - 1):
                folders.add(".".join(parts[: index + 1]))
        return folders

    def build_resource_tree_rows(self):
        manifest = self.load_resource_manifest()
        rows = []
        inserted = set()
        for folder_path in manifest.get("folders", []):
            parts = str(folder_path).split(".")
            parent_path = ""
            for index, part in enumerate(parts):
                path = ".".join(parts[: index + 1])
                parent_id = parent_path or ""
                if path not in inserted:
                    rows.append(
                        {
                            "id": path,
                            "parent": parent_id,
                            "text": self.format_resource_label(part, is_leaf=False),
                            "kind": "folder",
                            "value": "",
                        }
                    )
                    inserted.add(path)
                parent_path = path
        for resource_key, entry in sorted(manifest.get("resources", {}).items()):
            parts = str(resource_key).split(".")
            parent_path = ""
            for index, part in enumerate(parts):
                path = ".".join(parts[: index + 1])
                parent_id = parent_path or ""
                if path not in inserted:
                    is_leaf = index == len(parts) - 1
                    rows.append(
                        {
                            "id": path,
                            "parent": parent_id,
                            "text": self.format_resource_label(part, is_leaf),
                            "kind": "resource" if is_leaf else "folder",
                            "value": self.format_resource_value(entry) if is_leaf else "",
                        }
                    )
                    inserted.add(path)
                parent_path = path
        return rows

    @staticmethod
    def format_resource_value(entry):
        if not isinstance(entry, dict):
            return ""
        path = entry.get("path", "")
        width = entry.get("frame_width", "")
        height = entry.get("frame_height", "")
        return f"{path} [{width}x{height}]".strip()

    @staticmethod
    def format_resource_label(label, is_leaf):
        prefix = "[PNG]" if is_leaf else "[DIR]"
        return f"{prefix} {label}"

    def build_gui_explorer_nodes(self):
        nodes = []
        layout = screen_layout_config.load_screen_layout()
        groups_payload = group_config.load_group_config().get("groups", {})
        screens_payload = layout.get("screens", {})
        for screen_id, screen_payload in sorted(screens_payload.items()):
            screen_node_id = f"screen:{screen_id}"
            nodes.append(
                GuiExplorerNode(
                    node_id=screen_node_id,
                    kind="screen",
                    label=self.format_gui_label("screen", screen_id),
                    payload={"screen_id": screen_id},
                )
            )
            nodes.extend(self.build_screen_frame_nodes(screen_id))
            nodes.extend(self.build_screen_group_nodes(screen_id, screen_payload, groups_payload))
        return nodes

    def build_screen_frame_nodes(self, screen_id):
        layout = screen_layout_config.load_screen_layout()
        screen_payload = layout.get("screens", {}).get(screen_id, {})
        frame_specs = screen_payload.get("frames", {})
        if not isinstance(frame_specs, dict) or not frame_specs:
            if screen_id != "table_screen":
                return []
            frame_specs = self.get_table_screen_frame_specs()
        nodes = []
        for frame_id, spec in frame_specs.items():
            parent_frame_id = spec.get("parent_frame_id")
            nodes.append(
                GuiExplorerNode(
                    node_id=f"frame:{frame_id}",
                    kind="frame",
                    label=self.format_gui_label("frame", frame_id),
                    parent_id=f"frame:{parent_frame_id}" if parent_frame_id else f"screen:{screen_id}",
                    payload=dict(spec),
                )
            )
        return nodes

    def build_screen_group_nodes(self, screen_id, screen_payload, groups_payload):
        nodes = []
        groups = screen_payload.get("groups", {})
        if not isinstance(groups, dict):
            return nodes
        for group_id, placement in sorted(groups.items()):
            parent_frame_id = None
            if isinstance(placement, dict):
                parent_frame_id = placement.get("frame_id")
            group_payload = dict(groups_payload.get(group_id, {}))
            if isinstance(placement, dict):
                group_payload["placement"] = dict(placement)
                group_payload["screen_id"] = screen_id
            nodes.append(
                GuiExplorerNode(
                    node_id=f"group:{group_id}",
                    kind="group",
                    label=self.format_gui_label("group", group_id),
                    parent_id=f"frame:{parent_frame_id}" if parent_frame_id else f"screen:{screen_id}",
                    payload=group_payload,
                )
            )
        return nodes

    @staticmethod
    def format_gui_label(kind, label):
        prefixes = {
            "screen": "[SCREEN]",
            "frame": "[FRAME]",
            "group": "[GROUP]",
        }
        return f"{prefixes.get(kind, '[NODE]')} {label}"

    @staticmethod
    def get_table_screen_frame_specs():
        return {
            "game_table": {"frame_id": "game_table", "parent_frame_id": None},
            "play_area_frame": {"frame_id": "play_area_frame", "parent_frame_id": "game_table"},
            "cards_slot_frame": {"frame_id": "cards_slot_frame", "parent_frame_id": "play_area_frame"},
            "deck_frame": {"frame_id": "deck_frame", "parent_frame_id": "game_table"},
            "left_player_frame": {"frame_id": "left_player_frame", "parent_frame_id": "game_table"},
            "left_player_portrait": {"frame_id": "left_player_portrait", "parent_frame_id": "left_player_frame"},
            "left_player_hand": {"frame_id": "left_player_hand", "parent_frame_id": "left_player_frame"},
            "right_player_frame": {"frame_id": "right_player_frame", "parent_frame_id": "game_table"},
            "right_player_portrait": {"frame_id": "right_player_portrait", "parent_frame_id": "right_player_frame"},
            "right_player_hand": {"frame_id": "right_player_hand", "parent_frame_id": "right_player_frame"},
            "top_player_frame": {"frame_id": "top_player_frame", "parent_frame_id": "game_table"},
            "top_player_portrait": {"frame_id": "top_player_portrait", "parent_frame_id": "top_player_frame"},
            "top_player_hand": {"frame_id": "top_player_hand", "parent_frame_id": "top_player_frame"},
            "bottom_player_frame": {"frame_id": "bottom_player_frame", "parent_frame_id": "game_table"},
            "bottom_player_portrait": {"frame_id": "bottom_player_portrait", "parent_frame_id": "bottom_player_frame"},
            "bottom_player_hand": {"frame_id": "bottom_player_hand", "parent_frame_id": "bottom_player_frame"},
        }


class ViewStyleDialog(QDialog):
    def __init__(self, parent, themes, current_theme, on_change):
        super().__init__(parent)
        self._on_change = on_change
        self.setWindowTitle("Стиль отображения")
        self.setModal(False)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.theme_picker = QComboBox()
        self.theme_picker.addItems(list(themes))
        self.theme_picker.setCurrentText(current_theme)
        self.theme_picker.currentTextChanged.connect(self._on_change)
        form.addRow("Theme", self.theme_picker)
        layout.addLayout(form)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.hide)
        layout.addWidget(close_button, alignment=Qt.AlignRight)


class ResourceManifestTree(QTreeWidget):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    def dropEvent(self, event):
        target_item = self.itemAt(event.position().toPoint()) if hasattr(event, "position") else self.itemAt(event.pos())
        if target_item is None or target_item.text(1) != "folder":
            event.ignore()
            return
        moved = self.owner.move_selected_rm_nodes_to_folder(target_item.data(0, Qt.UserRole))
        if moved:
            event.acceptProposedAction()
        else:
            event.ignore()


class GuiEditorApp(QMainWindow):
    MIN_WIDTH = 760
    MIN_HEIGHT = 720
    THEME_OPTIONS = ("cyborg", "darkly")
    CREATE_PANEL_MARGINS = (12, 12, 12, 12)
    CREATE_PANEL_SPACING = 12
    CREATE_FORM_ROW_SPACING = 10
    CREATE_BLOCK_GAP = 18
    CREATE_LINE_EDIT_VERTICAL_PADDING = 8
    CREATE_BUTTON_HEIGHT = 36

    def __init__(self, service=None):
        super().__init__()
        self.service = service or GuiEditorDataService()
        self.theme_name = self.THEME_OPTIONS[0]
        self.default_add_png_dir = self.service.get_default_add_png_dir()
        self.style_dialog = None
        self.theme_actions = {}
        self.current_form_title = QLabel("CREATE")
        self.current_selection = QLabel("Nothing selected")
        self.rm_tree = None
        self.rm_new_folder_button = None
        self.rm_status_label = None
        self.rm_preview_label = None
        self.rm_preview_hint_label = None
        self.gui_tree = None
        self.gui_problem_node_ids = set()
        self.right_tabs = None
        self.left_panel = None
        self.explorer_panel = None
        self.main_splitter = None
        self.create_screen_id_input = None
        self.create_root_frame_id_input = None
        self.create_width_input = None
        self.create_height_input = None
        self.create_screen_button = None
        self.create_status_label = None
        self.create_frame_screen_id_input = None
        self.create_frame_id_input = None
        self.create_frame_parent_id_input = None
        self.create_frame_x_input = None
        self.create_frame_y_input = None
        self.create_frame_width_input = None
        self.create_frame_height_input = None
        self.create_frame_button = None
        self.create_frame_status_label = None
        self.create_group_screen_id_input = None
        self.create_group_id_input = None
        self.create_group_frame_id_input = None
        self.create_group_x_input = None
        self.create_group_y_input = None
        self.group_graphic_rows_container = None
        self.group_graphic_rows_layout = None
        self.group_graphic_resource_rows = []
        self.group_graphic_status_label = None
        self.group_text_value_input = None
        self.group_text_font_input = None
        self.group_text_size_input = None
        self.group_text_color_input = None
        self.group_text_status_label = None
        self.create_group_button = None
        self.create_group_status_label = None
        self._default_line_edit_style = None

        self._build_window()
        self._build_layout()
        self.reload_explorers()

    @classmethod
    def available_themes(cls):
        return cls.THEME_OPTIONS

    def _build_window(self):
        self.setWindowTitle("GUI Editor")
        self.setMinimumSize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self.resize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self._apply_theme(self.theme_name)

    def _build_layout(self):
        central = QWidget()
        self.setCentralWidget(central)

        outer = QVBoxLayout(central)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)
        outer.addWidget(self._build_toolbar())

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.addWidget(self._build_left_panel())
        self.main_splitter.addWidget(self._build_right_panel())
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 2)
        outer.addWidget(self.main_splitter, 1)

    def _build_toolbar(self):
        bar = QFrame()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 6, 8, 6)

        settings_button = QPushButton("Settings")
        menu = QMenu(self)
        view_style_menu = menu.addMenu("View Style")
        for theme_name in self.available_themes():
            action = QAction(theme_name, self)
            action.setCheckable(True)
            action.setChecked(theme_name == self.theme_name)
            action.triggered.connect(lambda _checked=False, value=theme_name: self._apply_theme(value))
            view_style_menu.addAction(action)
            self.theme_actions[theme_name] = action
        settings_button.setMenu(menu)
        layout.addWidget(settings_button)
        layout.addStretch(1)
        return bar

    def _build_left_panel(self):
        self.left_panel = QFrame()
        self.left_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        layout = QVBoxLayout(self.left_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._build_create_view_v2())
        return self.left_panel

    # Container/layout helpers
    def _build_create_view_v2(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.CREATE_PANEL_SPACING)
        layout.addWidget(self._title_label("Create/Edit entities"))
        layout.addWidget(self._build_create_screen_section())
        layout.addWidget(self._build_create_frame_section())
        layout.addWidget(self._build_create_group_section())
        layout.addStretch(1)
        scroll.setWidget(page)
        return scroll

    # CREATE composition helpers
    def _build_create_screen_section(self):
        box, outer = self._create_form_panel("Screen", "Create a screen and its root frame.")

        self.create_screen_id_input = self._form_line_edit()
        self.create_root_frame_id_input = self._form_line_edit()
        self.create_width_input = self._form_line_edit()
        self.create_height_input = self._form_line_edit()
        outer.addLayout(
            self._build_identity_block(
                (
                    ("screen_id", self.create_screen_id_input),
                    ("root_frame_id", self.create_root_frame_id_input),
                )
            )
        )
        outer.addSpacing(self.CREATE_BLOCK_GAP)
        outer.addLayout(
            self._build_geometry_block(
                (
                    ("width", self.create_width_input),
                    ("height", self.create_height_input),
                )
            )
        )

        actions = QHBoxLayout()
        actions.setSpacing(self.CREATE_PANEL_SPACING)
        self.create_screen_button = self._form_button("Save screen")
        self.create_screen_button.clicked.connect(self.create_screen_from_form)
        actions.addWidget(self.create_screen_button, alignment=Qt.AlignLeft)
        actions.addStretch(1)
        outer.addLayout(actions)
        outer.addSpacing(self.CREATE_BLOCK_GAP)

        self.create_status_label = self._muted_label("Waiting for screen parameters")
        outer.addWidget(self.create_status_label)
        return box

    def _build_create_frame_section(self):
        box, outer = self._create_form_panel("Frame", "Create a child frame inside a screen.")

        self.create_frame_screen_id_input = self._form_line_edit()
        self.create_frame_id_input = self._form_line_edit()
        self.create_frame_parent_id_input = self._form_line_edit()
        outer.addLayout(
            self._build_identity_block(
                (
                    ("screen_id", self.create_frame_screen_id_input),
                    ("frame_id", self.create_frame_id_input),
                    ("parent_frame_id", self.create_frame_parent_id_input),
                )
            )
        )
        outer.addSpacing(self.CREATE_BLOCK_GAP)

        self.create_frame_x_input = self._form_line_edit(compact=True)
        self.create_frame_y_input = self._form_line_edit(compact=True)
        self.create_frame_width_input = self._form_line_edit(compact=True)
        self.create_frame_height_input = self._form_line_edit(compact=True)
        outer.addLayout(
            self._build_geometry_block(
                (
                    ("x", self.create_frame_x_input),
                    ("y", self.create_frame_y_input),
                    ("width", self.create_frame_width_input),
                    ("height", self.create_frame_height_input),
                )
            )
        )

        actions = QHBoxLayout()
        actions.setSpacing(self.CREATE_PANEL_SPACING)
        self.create_frame_button = self._form_button("Save frame")
        self.create_frame_button.clicked.connect(self.create_frame_from_form)
        actions.addWidget(self.create_frame_button, alignment=Qt.AlignLeft)
        actions.addStretch(1)
        outer.addLayout(actions)
        outer.addSpacing(self.CREATE_BLOCK_GAP)

        self.create_frame_status_label = self._muted_label("Waiting for frame parameters")
        outer.addWidget(self.create_frame_status_label)
        return box

    def _build_create_group_section(self):
        box, outer = self._create_form_panel("Group", "Create a group and place it inside a frame.")

        self.create_group_screen_id_input = self._form_line_edit()
        self.create_group_id_input = self._form_line_edit()
        self.create_group_frame_id_input = self._form_line_edit()
        outer.addLayout(
            self._build_identity_block(
                (
                    ("screen_id", self.create_group_screen_id_input),
                    ("group_id", self.create_group_id_input),
                    ("frame_id", self.create_group_frame_id_input),
                )
            )
        )
        outer.addSpacing(self.CREATE_BLOCK_GAP)

        self.create_group_x_input = self._form_line_edit(compact=True)
        self.create_group_y_input = self._form_line_edit(compact=True)
        outer.addLayout(
            self._build_geometry_block(
                (
                    ("x", self.create_group_x_input),
                    ("y", self.create_group_y_input),
                )
            )
        )
        outer.addSpacing(self.CREATE_BLOCK_GAP)
        outer.addWidget(self._build_group_graphic_layer_panel())
        outer.addSpacing(self.CREATE_BLOCK_GAP)
        outer.addWidget(self._build_group_text_layer_panel())
        outer.addSpacing(self.CREATE_BLOCK_GAP)

        actions = QHBoxLayout()
        actions.setSpacing(self.CREATE_PANEL_SPACING)
        self.create_group_button = self._form_button("Save group")
        self.create_group_button.clicked.connect(self.create_group_from_form)
        actions.addWidget(self.create_group_button, alignment=Qt.AlignLeft)
        actions.addStretch(1)
        outer.addLayout(actions)
        outer.addSpacing(self.CREATE_BLOCK_GAP)

        self.create_group_status_label = self._muted_label("Waiting for group parameters")
        outer.addWidget(self.create_group_status_label)
        return box

    def _build_group_graphic_layer_panel(self):
        box, outer = self._create_form_panel("Graphic Layer", "Build one or more image layers from RM Explorer resources.")
        self.group_graphic_rows_container = QWidget()
        self.group_graphic_rows_layout = QVBoxLayout(self.group_graphic_rows_container)
        self.group_graphic_rows_layout.setContentsMargins(0, 0, 0, 0)
        self.group_graphic_rows_layout.setSpacing(self.CREATE_FORM_ROW_SPACING)
        outer.addWidget(self.group_graphic_rows_container)
        self._append_graphic_resource_row()
        outer.addSpacing(self.CREATE_BLOCK_GAP)

        self.group_graphic_status_label = self._muted_label("Use '+' to bind the selected RM resource, 'More' to add another row")
        outer.addWidget(self.group_graphic_status_label)
        return box

    def _build_group_text_layer_panel(self):
        box, outer = self._create_form_panel("Text Layer", "Configure the text layer displayed by the group.")
        self.group_text_value_input = self._form_line_edit()
        self.group_text_font_input = self._form_line_edit()
        outer.addLayout(
            self._build_identity_block(
                (
                    ("text", self.group_text_value_input),
                    ("font", self.group_text_font_input),
                )
            )
        )
        outer.addSpacing(self.CREATE_BLOCK_GAP)

        self.group_text_size_input = self._form_line_edit(compact=True)
        self.group_text_color_input = self._form_line_edit()
        outer.addLayout(
            self._build_geometry_block(
                (
                    ("size", self.group_text_size_input),
                    ("color", self.group_text_color_input),
                )
            )
        )
        outer.addSpacing(self.CREATE_BLOCK_GAP)
        self.group_text_status_label = self._muted_label("Waiting for text layer data")
        outer.addWidget(self.group_text_status_label)
        return box

    def add_selected_rm_resource_to_graphic_layer(self, target_entry=None):
        item = self.rm_tree.currentItem() if self.rm_tree is not None else None
        if item is None or item.text(1) != "resource":
            self.group_graphic_status_label.setText("Select a PNG resource in RM Explorer first")
            return None
        resource_key = item.data(0, Qt.UserRole)
        if not resource_key:
            self.group_graphic_status_label.setText("Selected RM node has no resource key")
            return None
        existing_keys = {
            row["entry"].text().strip()
            for row in self.group_graphic_resource_rows
            if row["entry"].text().strip()
        }
        if resource_key in existing_keys:
            self.group_graphic_status_label.setText(f"Resource already added: {resource_key}")
            self._focus_graphic_resource_entry(resource_key)
            return resource_key
        if target_entry is None:
            empty_row = next((row for row in self.group_graphic_resource_rows if not row["entry"].text().strip()), None)
            target_entry = empty_row["entry"] if empty_row is not None else self._append_graphic_resource_row()["entry"]
        target_entry.setText(resource_key)
        target_entry.setFocus()
        self.group_graphic_status_label.setText(f"Added graphic resource: {resource_key}")
        self._reveal_graphic_resource_in_rm(resource_key)
        return resource_key

    def remove_selected_graphic_resource(self, row_index=None):
        if not self.group_graphic_resource_rows:
            self.group_graphic_status_label.setText("No graphic resource rows to remove")
            return None
        if row_index is None:
            focused_row = next(
                (index for index, row in enumerate(self.group_graphic_resource_rows) if row["entry"].hasFocus()),
                None,
            )
            if focused_row is None:
                self.group_graphic_status_label.setText("Select a graphic resource row to remove")
                return None
            row_index = focused_row
        if row_index < 0 or row_index >= len(self.group_graphic_resource_rows):
            self.group_graphic_status_label.setText("Graphic resource row not found")
            return None
        row = self.group_graphic_resource_rows[row_index]
        resource_key = row["entry"].text().strip()
        if len(self.group_graphic_resource_rows) == 1:
            row["entry"].clear()
        else:
            row["widget"].setParent(None)
            row["widget"].deleteLater()
            self.group_graphic_resource_rows.pop(row_index)
        self.group_graphic_status_label.setText(f"Removed graphic resource: {resource_key}")
        return resource_key

    def _append_graphic_resource_row(self, resource_key=""):
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(self.CREATE_PANEL_SPACING)
        entry = self._form_line_edit()
        entry.setText(resource_key)
        entry.editingFinished.connect(lambda current_entry=entry: self._reveal_graphic_resource_entry_in_rm(current_entry))
        add_button = self._form_button("+")
        more_button = self._form_button("More")
        remove_button = self._form_button("-")
        row_index = len(self.group_graphic_resource_rows)
        add_button.clicked.connect(lambda _checked=False, current_entry=entry: self.add_selected_rm_resource_to_graphic_layer(current_entry))
        more_button.clicked.connect(lambda _checked=False: self._append_graphic_resource_row())
        remove_button.clicked.connect(lambda _checked=False, index=row_index: self.remove_selected_graphic_resource(index))
        row_layout.addWidget(QLabel("resource_key"), alignment=Qt.AlignLeft | Qt.AlignVCenter)
        row_layout.addWidget(entry, 1)
        row_layout.addWidget(add_button, alignment=Qt.AlignLeft)
        row_layout.addWidget(more_button, alignment=Qt.AlignLeft)
        row_layout.addWidget(remove_button, alignment=Qt.AlignLeft)
        row_data = {
            "widget": row_widget,
            "entry": entry,
            "add_button": add_button,
            "more_button": more_button,
            "remove_button": remove_button,
        }
        self.group_graphic_resource_rows.append(row_data)
        self.group_graphic_rows_layout.addWidget(row_widget)
        self._refresh_graphic_resource_row_callbacks()
        return row_data

    def _refresh_graphic_resource_row_callbacks(self):
        for index, row in enumerate(self.group_graphic_resource_rows):
            try:
                row["remove_button"].clicked.disconnect()
            except RuntimeError:
                pass
            except TypeError:
                pass
            row["remove_button"].clicked.connect(lambda _checked=False, current_index=index: self.remove_selected_graphic_resource(current_index))

    def _reveal_graphic_resource_entry_in_rm(self, entry):
        if entry is None:
            return None
        resource_key = entry.text().strip()
        if not resource_key:
            return None
        return self._reveal_graphic_resource_in_rm(resource_key)

    def _reveal_graphic_resource_in_rm(self, resource_key):
        self.right_tabs.setCurrentIndex(0)
        return self._select_rm_node(resource_key, expand_parents=True)

    def _focus_graphic_resource_entry(self, resource_key):
        if not resource_key:
            return None
        for row in self.group_graphic_resource_rows:
            if row["entry"].text().strip() == resource_key:
                row["entry"].setFocus()
                return row["entry"]
        return None

    # Shared form-composition helpers
    def _create_form_panel(self, title, description):
        box = QFrame()
        box.setProperty("panel", True)
        box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        outer = QVBoxLayout(box)
        outer.setContentsMargins(*self.CREATE_PANEL_MARGINS)
        outer.setSpacing(self.CREATE_PANEL_SPACING)
        outer.addWidget(self._title_label(title))
        outer.addWidget(self._muted_label(description))
        return box, outer

    def _build_identity_block(self, rows):
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(self.CREATE_PANEL_SPACING)
        grid.setVerticalSpacing(self.CREATE_FORM_ROW_SPACING)
        for index, (label, widget) in enumerate(rows):
            grid.addWidget(QLabel(label), index, 0, alignment=Qt.AlignLeft | Qt.AlignVCenter)
            grid.addWidget(widget, index, 1)
        grid.setRowMinimumHeight(len(rows), 0)
        grid.setColumnStretch(1, 1)
        return grid

    def _build_geometry_block(self, fields):
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(self.CREATE_PANEL_SPACING)
        grid.setVerticalSpacing(self.CREATE_FORM_ROW_SPACING)
        for index, (label, widget) in enumerate(fields):
            row = index // 2
            column = (index % 2) * 2
            grid.addWidget(QLabel(label), row, column, alignment=Qt.AlignLeft | Qt.AlignVCenter)
            grid.addWidget(widget, row, column + 1)
        grid.setColumnStretch(4, 1)
        return grid

    # Shared control-metric helpers
    def _form_button(self, text):
        button = QPushButton(text)
        button.setMinimumHeight(self.CREATE_BUTTON_HEIGHT)
        button.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        return button

    @staticmethod
    def _form_line_edit(compact=False):
        entry = QLineEdit()
        line_height = entry.fontMetrics().height() + GuiEditorApp.CREATE_LINE_EDIT_VERTICAL_PADDING
        entry.setMinimumHeight(line_height)
        entry.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        if compact:
            entry.setMaximumWidth(96)
        return entry

    def _build_rect_form(self, title):
        box = QFrame()
        box.setProperty("panel", True)
        outer = QVBoxLayout(box)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.addWidget(self._title_label(title))
        row = QHBoxLayout()
        for label in ("X", "Y", "W", "H"):
            row.addWidget(QLabel(label))
            entry = QLineEdit()
            entry.setFixedWidth(52)
            row.addWidget(entry)
        row.addStretch(1)
        outer.addLayout(row)
        return box

    def _labeled_line(self, label):
        box = QFrame()
        layout = QFormLayout(box)
        layout.addRow(label, QLineEdit())
        return box

    # Right-panel container helpers
    def _build_right_panel(self):
        self.explorer_panel = QFrame()
        self.explorer_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        layout = QVBoxLayout(self.explorer_panel)
        layout.setContentsMargins(0, 0, 0, 0)

        self.right_tabs = QTabWidget()
        self.right_tabs.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.right_tabs.addTab(self._build_rm_manifest_view(), "RM Manifest Explorer")
        self.right_tabs.addTab(self._build_gui_explorer_view(), "GUI Explorer")
        layout.addWidget(self.right_tabs)
        return self.explorer_panel

    def _build_rm_manifest_view(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._title_label("RM Manifest Explorer"))
        self.rm_tree = ResourceManifestTree(self)
        self.rm_tree.setColumnCount(2)
        self.rm_tree.setHeaderLabels(["Manifest Node", "Type"])
        self.rm_tree.setRootIsDecorated(True)
        self.rm_tree.setIndentation(18)
        self.rm_tree.setUniformRowHeights(True)
        self.rm_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.rm_tree.setDragEnabled(True)
        self.rm_tree.viewport().setAcceptDrops(True)
        self.rm_tree.setDropIndicatorShown(True)
        self.rm_tree.setDragDropMode(QAbstractItemView.InternalMove)
        self.rm_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.rm_tree.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.rm_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.rm_tree.header().setStretchLastSection(False)
        self.rm_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.rm_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.rm_tree.itemSelectionChanged.connect(self.on_rm_select)
        self.rm_tree.customContextMenuRequested.connect(self.open_rm_context_menu)
        self.rm_tree.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        layout.addWidget(self.rm_tree, 1)

        layout.addWidget(self._build_rm_preview_panel())
        self.rm_status_label = self._muted_label("Waiting for RM action")
        layout.addWidget(self.rm_status_label)
        return page

    def _build_rm_preview_panel(self):
        box = QFrame()
        box.setProperty("panel", True)
        outer = QVBoxLayout(box)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)
        outer.addWidget(self._title_label("Preview"))
        self.rm_preview_label = QLabel("No PNG selected")
        self.rm_preview_label.setAlignment(Qt.AlignCenter)
        self.rm_preview_label.setMinimumSize(180, 120)
        self.rm_preview_label.setProperty("preview", True)
        self.rm_preview_hint_label = self._muted_label("Select a PNG leaf in RM Manifest Explorer")
        outer.addWidget(self.rm_preview_label)
        outer.addWidget(self.rm_preview_hint_label)
        return box

    def _build_gui_explorer_view(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._title_label("GUI Explorer"))
        self.gui_tree = QTreeWidget()
        self.gui_tree.setColumnCount(1)
        self.gui_tree.setHeaderLabels(["Node"])
        self.gui_tree.setRootIsDecorated(True)
        self.gui_tree.setIndentation(18)
        self.gui_tree.setUniformRowHeights(True)
        self.gui_tree.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.gui_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.gui_tree.header().setStretchLastSection(False)
        self.gui_tree.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.gui_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.gui_tree.itemSelectionChanged.connect(self.on_gui_select)
        self.gui_tree.customContextMenuRequested.connect(self.open_gui_context_menu)
        layout.addWidget(self.gui_tree)
        return page

    def reload_explorers(self):
        self.populate_rm_tree()
        self.populate_gui_tree()
        self._stabilize_right_panel_width()
        self._apply_window_geometry_contract()

    def create_screen_from_form(self):
        self._clear_create_validation()
        screen_id = self.create_screen_id_input.text().strip()
        root_frame_id = self.create_root_frame_id_input.text().strip()
        width_text = self.create_width_input.text().strip()
        height_text = self.create_height_input.text().strip()
        if not screen_id or not root_frame_id:
            self._mark_invalid_fields(
                self.create_screen_id_input if not screen_id else None,
                self.create_root_frame_id_input if not root_frame_id else None,
            )
            self.create_status_label.setText("screen_id and root_frame_id are required")
            return None
        try:
            width = int(width_text)
            height = int(height_text)
        except ValueError:
            self._mark_invalid_fields(self.create_width_input, self.create_height_input)
            self.create_status_label.setText("width and height must be integers")
            return None
        if width <= 0 or height <= 0:
            self._mark_invalid_fields(
                self.create_width_input if width <= 0 else None,
                self.create_height_input if height <= 0 else None,
            )
            self.create_status_label.setText("width and height must be positive")
            return None

        blocking_nodes = self._collect_screen_geometry_conflicts(screen_id, root_frame_id, (width, height))
        if blocking_nodes:
            self._show_gui_geometry_conflicts(
                blocking_nodes,
                "Cannot save screen geometry because the screen already has nested objects that would be implicitly recalculated.",
            )
            self.create_status_label.setText("Screen geometry save blocked by nested GUI objects")
            return None

        payload = screen_layout_config.upsert_screen(screen_id, root_frame_id, (width, height))
        screen_layout_config.save_screen_layout(payload)
        self.gui_problem_node_ids.clear()
        self.reload_explorers()
        self._select_gui_node(f"screen:{screen_id}", expand_parents=True)
        self.create_status_label.setText(f"Created screen: {screen_id}")
        self.current_selection.setText(f"Created screen: {screen_id}")
        return payload

    def create_frame_from_form(self):
        if self.gui_tree is not None and self.gui_tree.currentItem() is not None and not self.validate_create_context_from_gui("frame"):
            return None
        self._clear_create_validation()
        screen_id = self.create_frame_screen_id_input.text().strip()
        frame_id = self.create_frame_id_input.text().strip()
        parent_frame_id = self.create_frame_parent_id_input.text().strip()
        x_text = self.create_frame_x_input.text().strip()
        y_text = self.create_frame_y_input.text().strip()
        width_text = self.create_frame_width_input.text().strip()
        height_text = self.create_frame_height_input.text().strip()
        if not screen_id or not frame_id or not parent_frame_id:
            self._mark_invalid_fields(
                self.create_frame_screen_id_input if not screen_id else None,
                self.create_frame_id_input if not frame_id else None,
                self.create_frame_parent_id_input if not parent_frame_id else None,
            )
            self.create_frame_status_label.setText("screen_id, frame_id and parent_frame_id are required")
            return None
        payload = screen_layout_config.load_screen_layout()
        screen_payload = payload.get("screens", {}).get(screen_id)
        if not isinstance(screen_payload, dict):
            self._mark_invalid_fields(self.create_frame_screen_id_input)
            self.create_frame_status_label.setText(f"Unknown screen: {screen_id}")
            return None
        frames = screen_payload.get("frames", {})
        if parent_frame_id not in frames:
            self._mark_invalid_fields(self.create_frame_parent_id_input)
            self.create_frame_status_label.setText(f"Unknown parent frame: {parent_frame_id}")
            return None
        try:
            rect = (
                int(x_text),
                int(y_text),
                int(width_text),
                int(height_text),
            )
        except ValueError:
            self._mark_invalid_fields(
                self.create_frame_x_input,
                self.create_frame_y_input,
                self.create_frame_width_input,
                self.create_frame_height_input,
            )
            self.create_frame_status_label.setText("x, y, width and height must be integers")
            return None
        if rect[2] <= 0 or rect[3] <= 0:
            self._mark_invalid_fields(
                self.create_frame_width_input if rect[2] <= 0 else None,
                self.create_frame_height_input if rect[3] <= 0 else None,
            )
            self.create_frame_status_label.setText("width and height must be positive")
            return None

        blocking_nodes = self._collect_frame_geometry_conflicts(screen_id, frame_id, rect)
        if blocking_nodes:
            self._show_gui_geometry_conflicts(
                blocking_nodes,
                "Cannot save frame geometry because the frame already has nested objects that would be implicitly recalculated.",
            )
            self.create_frame_status_label.setText("Frame geometry save blocked by nested GUI objects")
            return None

        payload = screen_layout_config.upsert_frame(screen_id, frame_id, parent_frame_id, rect, payload=payload)
        screen_layout_config.save_screen_layout(payload)
        self.gui_problem_node_ids.clear()
        self.reload_explorers()
        self._select_gui_node(f"frame:{frame_id}", expand_parents=True)
        self.create_frame_status_label.setText(f"Created frame: {frame_id}")
        self.current_selection.setText(f"Created frame: {frame_id}")
        return payload

    def create_group_from_form(self):
        if self.gui_tree is not None and self.gui_tree.currentItem() is not None and not self.validate_create_context_from_gui("group"):
            return None
        self._clear_create_validation()
        screen_id = self.create_group_screen_id_input.text().strip()
        group_id = self.create_group_id_input.text().strip()
        frame_id = self.create_group_frame_id_input.text().strip()
        x_text = self.create_group_x_input.text().strip()
        y_text = self.create_group_y_input.text().strip()
        if not screen_id or not group_id or not frame_id:
            self._mark_invalid_fields(
                self.create_group_screen_id_input if not screen_id else None,
                self.create_group_id_input if not group_id else None,
                self.create_group_frame_id_input if not frame_id else None,
            )
            self.create_group_status_label.setText("screen_id, group_id and frame_id are required")
            return None

        screen_payload = screen_layout_config.load_screen_layout().get("screens", {}).get(screen_id)
        if not isinstance(screen_payload, dict):
            self._mark_invalid_fields(self.create_group_screen_id_input)
            self.create_group_status_label.setText(f"Unknown screen: {screen_id}")
            return None
        frames = screen_payload.get("frames", {})
        if frame_id not in frames and not (screen_id == "table_screen" and frame_id in self.service.get_table_screen_frame_specs()):
            self._mark_invalid_fields(self.create_group_frame_id_input)
            self.create_group_status_label.setText(f"Unknown frame: {frame_id}")
            return None
        try:
            position = (int(x_text), int(y_text))
        except ValueError:
            self._mark_invalid_fields(self.create_group_x_input, self.create_group_y_input)
            self.create_group_status_label.setText("x and y must be integers")
            return None

        group_config.reload_group_config()
        existing_group_payload = dict(group_config.GROUP_CONFIG.get("groups", {}).get(group_id, {}))
        group_config.ensure_group(group_id)
        try:
            layers, layer_inputs_provided = self._build_group_layers_from_form()
        except ValueError as error:
            self.create_group_status_label.setText(str(error))
            return None
        group_updates = {}
        if layer_inputs_provided:
            group_updates["layers"] = layers
        if group_updates:
            group_config.upsert_group(group_id, group_updates)
        else:
            group_config.save_group_config()

        payload = screen_layout_config.upsert_group_placement(group_id, screen_id, frame_id, position=position)
        screen_layout_config.save_screen_layout(payload)
        self.gui_problem_node_ids.clear()
        self.reload_explorers()
        self._select_gui_node(f"group:{group_id}", expand_parents=True)
        if layer_inputs_provided:
            if group_updates.get("layers"):
                self.group_graphic_status_label.setText(f"Saved {len([layer for layer in group_updates['layers'] if layer.get('type') != 'text'])} graphic layer(s)")
                text_layers = [layer for layer in group_updates["layers"] if layer.get("type") == "text"]
                self.group_text_status_label.setText("Saved text layer" if text_layers else "Text layer cleared")
            else:
                self.group_graphic_status_label.setText("Graphic layers cleared")
                self.group_text_status_label.setText("Text layer cleared")
        elif existing_group_payload.get("layers"):
            self.group_graphic_status_label.setText("Preserved existing group layers")
            self.group_text_status_label.setText("Preserved existing text layer")
        self.create_group_status_label.setText(f"Created group: {group_id}")
        self.current_selection.setText(f"Created group: {group_id}")
        return payload

    def _build_group_layers_from_form(self):
        manifest_resources = self.service.load_resource_manifest().get("resources", {})
        graphic_layers = []
        layer_inputs_provided = False
        for index, row in enumerate(self.group_graphic_resource_rows, start=1):
            resource_key = row["entry"].text().strip()
            if not resource_key:
                continue
            layer_inputs_provided = True
            if resource_key not in manifest_resources:
                self._mark_invalid_fields(row["entry"])
                raise ValueError(f"Unknown graphic resource: {resource_key}")
            graphic_layers.append(
                {
                    "name": f"graphic_layer_{index}",
                    "type": "image",
                    "resource_key": resource_key,
                    "position": [0, 0],
                }
            )

        text_value = self.group_text_value_input.text().strip()
        font_value = self.group_text_font_input.text().strip()
        size_value = self.group_text_size_input.text().strip()
        color_value = self.group_text_color_input.text().strip()
        text_inputs_provided = any((text_value, font_value, size_value, color_value))
        text_layers = []
        if text_inputs_provided:
            layer_inputs_provided = True
            text_layer = {
                "name": "text_layer",
                "type": "text",
                "text": text_value,
                "position": [0, 0],
            }
            if size_value:
                text_layer["size"] = list(self._parse_group_text_size(size_value))
            if font_value or color_value:
                style = {}
                if font_value:
                    style["font_name"] = font_value
                if color_value:
                    style["color"] = list(self._parse_group_text_color(color_value))
                if style:
                    text_layer["style"] = style
            text_layers.append(text_layer)

        return graphic_layers + text_layers, layer_inputs_provided

    def _parse_group_text_size(self, raw_value):
        normalized = str(raw_value).lower().replace("x", ",")
        parts = [part.strip() for part in normalized.split(",") if part.strip()]
        if len(parts) != 2:
            self._mark_invalid_fields(self.group_text_size_input)
            raise ValueError("Text size must be 'width,height'")
        try:
            width = int(parts[0])
            height = int(parts[1])
        except ValueError as error:
            self._mark_invalid_fields(self.group_text_size_input)
            raise ValueError("Text size must be 'width,height'") from error
        return width, height

    def _parse_group_text_color(self, raw_value):
        parts = [part.strip() for part in str(raw_value).split(",") if part.strip()]
        if len(parts) != 3:
            self._mark_invalid_fields(self.group_text_color_input)
            raise ValueError("Text color must be 'r,g,b'")
        try:
            color = tuple(int(part) for part in parts)
        except ValueError as error:
            self._mark_invalid_fields(self.group_text_color_input)
            raise ValueError("Text color must be 'r,g,b'") from error
        if any(component < 0 or component > 255 for component in color):
            self._mark_invalid_fields(self.group_text_color_input)
            raise ValueError("Text color must use values from 0 to 255")
        return color

    def populate_rm_tree(self):
        self.rm_tree.clear()
        items = {}
        for row in self.service.build_resource_tree_rows():
            item = QTreeWidgetItem([row["text"], row["kind"]])
            item.setData(0, Qt.UserRole, row["id"])
            parent_id = row["parent"]
            if parent_id and parent_id in items:
                items[parent_id].addChild(item)
            else:
                self.rm_tree.addTopLevelItem(item)
            items[row["id"]] = item
            depth = items[parent_id].data(0, Qt.UserRole + 10) + 1 if parent_id and parent_id in items else 0
            item.setData(0, Qt.UserRole + 10, depth)
            self._apply_item_depth_style(item, depth)
            item.setExpanded(False)
        self._autosize_qtree(self.rm_tree)
        first_column_width = self.rm_tree.columnWidth(0)
        self.rm_tree.setColumnWidth(0, first_column_width + 40)

    def add_png_from_dialog(self):
        selected_path, _filter = QFileDialog.getOpenFileName(
            self,
            "Select PNG",
            self.default_add_png_dir or self.service.assets_dir,
            "PNG Files (*.png)",
        )
        if not selected_path:
            self.rm_status_label.setText("PNG selection cancelled")
            return None
        selected_dir = os.path.dirname(selected_path) or self.service.assets_dir
        manifest_path = None
        current_item = self.rm_tree.currentItem() if self.rm_tree is not None else None
        clicked_item = None
        if self.rm_tree is not None:
            clicked_item = self.rm_tree.itemAt(self.rm_tree.viewport().mapFromGlobal(QCursor.pos()))
        target_item = clicked_item or current_item
        if target_item is not None and target_item.text(1) == "folder":
            folder_id = target_item.data(0, Qt.UserRole)
            file_name = os.path.basename(selected_path)
            resource_name = os.path.splitext(file_name)[0]
            manifest_path = f"{folder_id.replace('.', '/')}/{resource_name}.png"
        try:
            resource_key, entry = self.service.add_png_to_manifest(selected_path, manifest_path=manifest_path)
        except ValueError as error:
            self.rm_status_label.setText(str(error))
            return None
        if os.path.abspath(selected_dir) != os.path.abspath(self.default_add_png_dir or ""):
            answer = QMessageBox.question(
                self,
                "Default Add PNG folder",
                "Use this folder as default for Add PNG?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer == QMessageBox.Yes:
                self.default_add_png_dir = self.service.set_default_add_png_dir(selected_dir)
        self.reload_explorers()
        self._select_rm_node(resource_key, expand_parents=True)
        self.rm_status_label.setText(f"Added PNG: {resource_key}")
        self.current_selection.setText(f"RM entry: {entry['path']}")
        return resource_key

    def delete_selected_png(self, resource_key=None):
        item = self.rm_tree.currentItem()
        if resource_key is None:
            if item is None:
                self.rm_status_label.setText("Select a PNG entry first")
                return None
            resource_key = item.data(0, Qt.UserRole)
            if item.text(1) != "resource" or not resource_key:
                self.rm_status_label.setText("Select a PNG leaf entry first")
                return None
        removed_entry = self.service.remove_png_from_manifest(resource_key)
        if removed_entry is None:
            self.rm_status_label.setText(f"Manifest entry not found: {resource_key}")
            return None
        self.reload_explorers()
        self._clear_rm_preview()
        self.rm_status_label.setText(f"Deleted PNG: {resource_key}")
        self.current_selection.setText(f"Removed RM entry: {removed_entry['path']}")
        return resource_key

    def create_folder_from_dialog(self):
        parent_folder = None
        current_item = self.rm_tree.currentItem()
        if (
            current_item is not None
            and current_item.text(1) == "folder"
            and self.rm_tree.itemAt(self.rm_tree.viewport().mapFromGlobal(QCursor.pos())) is current_item
        ):
            parent_folder = current_item.data(0, Qt.UserRole)
        folder_name, accepted = QInputDialog.getText(self, "Create folder", "Folder name")
        if not accepted:
            self.rm_status_label.setText("Folder creation cancelled")
            return None
        try:
            folder_name = self.service.normalize_folder_path(folder_name).split(".")[-1]
            target_folder = f"{parent_folder}.{folder_name}" if parent_folder else folder_name
            folder_id, _folders = self.service.create_manifest_folder(target_folder)
        except ValueError as error:
            self.rm_status_label.setText(str(error))
            return None
        self.reload_explorers()
        self._select_rm_node(folder_id, expand_parents=True)
        self.rm_status_label.setText(f"Created folder: {folder_id}")
        self.current_selection.setText(f"Created folder: {folder_id}")
        return folder_id

    def rename_folder_from_dialog(self, folder_id=None):
        item = self.rm_tree.currentItem()
        if folder_id is None:
            if item is None or item.text(1) != "folder":
                self.rm_status_label.setText("Select a folder first")
                return None
            folder_id = item.data(0, Qt.UserRole)
        default_name = str(folder_id).split(".")[-1]
        new_name, accepted = QInputDialog.getText(self, "Rename folder", "Folder name", text=default_name)
        if not accepted:
            self.rm_status_label.setText("Folder rename cancelled")
            return None
        try:
            renamed_folder_id = self.service.rename_manifest_folder(folder_id, new_name)
        except ValueError as error:
            self.rm_status_label.setText(str(error))
            return None
        self.reload_explorers()
        self._select_rm_node(renamed_folder_id, expand_parents=True)
        self.rm_status_label.setText(f"Renamed folder: {renamed_folder_id}")
        self.current_selection.setText(f"Renamed folder: {renamed_folder_id}")
        return renamed_folder_id

    def rename_resource_from_dialog(self, resource_key=None):
        item = self.rm_tree.currentItem()
        if resource_key is None:
            if item is None or item.text(1) != "resource":
                self.rm_status_label.setText("Select a PNG entry first")
                return None
            resource_key = item.data(0, Qt.UserRole)
        default_name = str(resource_key).split(".")[-1]
        new_name, accepted = QInputDialog.getText(self, "Rename", "Name", text=default_name)
        if not accepted:
            self.rm_status_label.setText("Rename cancelled")
            return None
        try:
            renamed_resource_key = self.service.rename_manifest_resource(resource_key, new_name)
        except ValueError as error:
            self.rm_status_label.setText(str(error))
            return None
        self.reload_explorers()
        self._select_rm_node(renamed_resource_key, expand_parents=True)
        self.rm_status_label.setText(f"Renamed entry: {renamed_resource_key}")
        self.current_selection.setText(f"Renamed RM entry: {renamed_resource_key}")
        return renamed_resource_key

    def delete_folder_from_rm(self, folder_id=None):
        item = self.rm_tree.currentItem()
        if folder_id is None:
            if item is None or item.text(1) != "folder":
                self.rm_status_label.setText("Select a folder first")
                return None
            folder_id = item.data(0, Qt.UserRole)
        removed_folder_id = self.service.remove_manifest_folder(folder_id)
        if removed_folder_id is None:
            self.rm_status_label.setText(f"Manifest folder not found: {folder_id}")
            return None
        self.reload_explorers()
        self.rm_status_label.setText(f"Deleted folder: {removed_folder_id}")
        self.current_selection.setText(f"Removed RM folder: {removed_folder_id}")
        return removed_folder_id

    def delete_rm_node(self, node_id=None, kind=None):
        item = self.rm_tree.currentItem()
        if node_id is None or kind is None:
            if item is None:
                self.rm_status_label.setText("Select an RM entry first")
                return None
            node_id = item.data(0, Qt.UserRole)
            kind = item.text(1)
        if not node_id or kind not in {"folder", "resource"}:
            self.rm_status_label.setText("Select an RM entry first")
            return None
        answer = QMessageBox.question(
            self,
            "Delete",
            f"Delete '{node_id}' from RM manifest?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            self.rm_status_label.setText("Delete cancelled")
            return None
        if kind == "folder":
            return self.delete_folder_from_rm(node_id)
        return self.delete_selected_png(node_id)

    def move_selected_rm_nodes_to_folder(self, target_folder_id):
        selected_items = self.rm_tree.selectedItems()
        node_ids = [
            item.data(0, Qt.UserRole)
            for item in selected_items
            if item is not None and item.data(0, Qt.UserRole) and item.text(1) in {"folder", "resource"}
        ]
        if not node_ids:
            self.rm_status_label.setText("Select manifest nodes first")
            return None
        filtered_ids = []
        for node_id in sorted(set(node_ids), key=lambda value: (value.count("."), value)):
            if any(node_id.startswith(f"{parent_id}.") for parent_id in filtered_ids):
                continue
            filtered_ids.append(node_id)
        try:
            target_folder_id = self.service.move_manifest_nodes(filtered_ids, target_folder_id)
        except ValueError as error:
            self.rm_status_label.setText(str(error))
            return None
        self.reload_explorers()
        self._select_rm_node(target_folder_id, expand_parents=True)
        self.rm_status_label.setText(f"Moved nodes to: {target_folder_id}")
        self.current_selection.setText(f"Moved {len(filtered_ids)} RM node(s)")
        return target_folder_id

    def open_rm_context_menu(self, position):
        item = self.rm_tree.itemAt(position)
        menu = QMenu(self)
        create_action = menu.addAction("Create Folder")
        chosen = None
        rename_action = None
        delete_action = None
        add_png_action = menu.addAction("Add PNG")
        if item is not None and item.text(1) in {"folder", "resource"}:
            rename_action = menu.addAction("Rename")
            delete_action = menu.addAction("Delete")
        chosen = menu.exec(self.rm_tree.viewport().mapToGlobal(position))
        if chosen == add_png_action:
            if item is not None:
                self.rm_tree.setCurrentItem(item)
            self.add_png_from_dialog()
        elif chosen == create_action:
            if item is not None:
                self.rm_tree.setCurrentItem(item)
            self.create_folder_from_dialog()
        elif rename_action is not None and chosen == rename_action:
            self.rm_tree.setCurrentItem(item)
            if item.text(1) == "folder":
                self.rename_folder_from_dialog(item.data(0, Qt.UserRole))
            else:
                self.rename_resource_from_dialog(item.data(0, Qt.UserRole))
        elif delete_action is not None and chosen == delete_action:
            self.rm_tree.setCurrentItem(item)
            self.delete_rm_node(item.data(0, Qt.UserRole), item.text(1))

    def _select_rm_node(self, node_id, expand_parents=False):
        if not node_id:
            return None
        matches = self.rm_tree.findItems("", Qt.MatchContains | Qt.MatchRecursive, 0)
        for item in matches:
            if item.data(0, Qt.UserRole) != node_id:
                continue
            if expand_parents:
                parent = item.parent()
                while parent is not None:
                    parent.setExpanded(True)
                    parent = parent.parent()
            self.rm_tree.setCurrentItem(item)
            self.rm_tree.scrollToItem(item)
            return item
        return None

    def _select_gui_node(self, node_id, expand_parents=False):
        if not node_id:
            return None
        matches = self.gui_tree.findItems("", Qt.MatchContains | Qt.MatchRecursive, 0)
        for item in matches:
            if item.data(0, Qt.UserRole) != node_id:
                continue
            if expand_parents:
                parent = item.parent()
                while parent is not None:
                    parent.setExpanded(True)
                    parent = parent.parent()
            self.gui_tree.setCurrentItem(item)
            self.gui_tree.scrollToItem(item)
            return item
        return None

    def populate_gui_tree(self):
        self.gui_tree.clear()
        items = {}
        for node in self.service.build_gui_explorer_nodes():
            item = QTreeWidgetItem([node.label])
            item.setData(0, Qt.UserRole, node.node_id)
            item.setData(0, Qt.UserRole + 1, node.kind)
            parent_id = node.parent_id
            if parent_id and parent_id in items:
                items[parent_id].addChild(item)
            else:
                self.gui_tree.addTopLevelItem(item)
            items[node.node_id] = item
            if parent_id and parent_id in items:
                parent_depth = items[parent_id].data(0, Qt.UserRole + 10)
                if not isinstance(parent_depth, int):
                    parent_depth = 0
                depth = parent_depth + 1
            else:
                depth = 0
            item.setData(0, Qt.UserRole + 10, depth)
            self._apply_item_depth_style(item, depth)
            if node.node_id in self.gui_problem_node_ids:
                self._apply_problem_item_style(item)
            item.setExpanded(False)
        self._autosize_qtree(self.gui_tree)

    def _autosize_qtree(self, tree):
        for column in range(tree.columnCount()):
            tree.resizeColumnToContents(column)
            tree.setColumnWidth(column, tree.columnWidth(column) + 6)
        tree.updateGeometry()

    def _stabilize_right_panel_width(self, _index=None):
        if self.rm_tree is None or self.gui_tree is None or self.right_tabs is None or self.explorer_panel is None:
            return
        tree_width = max(self._qtree_total_width(self.rm_tree), self._qtree_total_width(self.gui_tree))
        tabs_width = self.right_tabs.tabBar().sizeHint().width() + 8
        explorer_width = max(tree_width, tabs_width) + 10
        self.right_tabs.setMinimumWidth(explorer_width)
        self.right_tabs.updateGeometry()

    def _apply_window_geometry_contract(self):
        return

    @staticmethod
    def _qtree_total_width(tree):
        header = tree.header()
        content_width = sum(max(header.sectionSize(index), tree.sizeHintForColumn(index)) for index in range(tree.columnCount()))
        scrollbar_width = tree.style().pixelMetric(QStyle.PM_ScrollBarExtent)
        frame_width = tree.frameWidth() * 2
        return content_width + scrollbar_width + frame_width + 8

    def _apply_item_depth_style(self, item, depth):
        background_hex, foreground_hex = self._depth_palette(depth)
        background = QBrush(QColor(background_hex))
        foreground = QBrush(QColor(foreground_hex))
        font = QFont(item.font(0))
        font.setBold(depth == 0)
        for column in range(item.columnCount()):
            item.setBackground(column, background)
            item.setForeground(column, foreground)
            item.setFont(column, font)

    @staticmethod
    def _apply_problem_item_style(item):
        warning_background = QBrush(QColor("#5a1f1f"))
        warning_foreground = QBrush(QColor("#ffd7d7"))
        font = QFont(item.font(0))
        font.setBold(True)
        for column in range(item.columnCount()):
            item.setBackground(column, warning_background)
            item.setForeground(column, warning_foreground)
            item.setFont(column, font)

    def _depth_palette(self, depth):
        darkly_palette = (
            ("#28384a", "#eaf4ff"),
            ("#233142", "#cde7ff"),
            ("#202c39", "#bfe3d2"),
            ("#1d2732", "#e6d5a8"),
            ("#1a222c", "#d9c1ff"),
        )
        cyborg_palette = (
            ("#173246", "#eef9ff"),
            ("#1b2d3b", "#d2efff"),
            ("#1e2934", "#caf0dd"),
            ("#202530", "#ffe2ae"),
            ("#232330", "#e0cbff"),
        )
        palette = darkly_palette if self.theme_name == "darkly" else cyborg_palette
        return palette[min(depth, len(palette) - 1)]

    def on_rm_select(self):
        items = self.rm_tree.selectedItems()
        if not items:
            self._clear_rm_preview()
            return
        item = self.rm_tree.currentItem() or items[0]
        if item.text(1) == "resource":
            self.current_selection.setText(f"Selected resource: {item.data(0, Qt.UserRole)}")
            self._update_rm_preview(item.data(0, Qt.UserRole))
        elif item.text(1) == "folder":
            self.current_selection.setText(f"Selected folder: {item.data(0, Qt.UserRole)}")
            self._clear_rm_preview()

    def _update_rm_preview(self, resource_key):
        manifest = self.service.load_resource_manifest()
        entry = manifest.get("resources", {}).get(resource_key)
        if not isinstance(entry, dict):
            self._clear_rm_preview()
            return
        relative_path = entry.get("path", "")
        file_path = os.path.join(self.service.assets_dir, relative_path.replace("/", os.sep))
        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            self.rm_preview_label.setText("Preview unavailable")
            self.rm_preview_label.setPixmap(QPixmap())
            self.rm_preview_hint_label.setText(relative_path or "PNG path missing")
            return
        scaled = pixmap.scaled(
            self.rm_preview_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.rm_preview_label.setText("")
        self.rm_preview_label.setPixmap(scaled)
        self.rm_preview_hint_label.setText(relative_path)

    def _clear_rm_preview(self):
        if self.rm_preview_label is None or self.rm_preview_hint_label is None:
            return
        self.rm_preview_label.setPixmap(QPixmap())
        self.rm_preview_label.setText("No PNG selected")
        self.rm_preview_hint_label.setText("Select a PNG leaf in RM Manifest Explorer")

    def on_gui_select(self):
        items = self.gui_tree.selectedItems()
        if not items:
            return
        item = items[0]
        kind = item.data(0, Qt.UserRole + 1) or "node"
        label = item.text(0)
        self.current_selection.setText(f"Selected {kind}: {label}")

    def open_gui_context_menu(self, position):
        item = self.gui_tree.itemAt(position)
        if item is None:
            return
        menu = QMenu(self)
        run_action = None
        use_in_create_action = menu.addAction("Use in Create/Edit")
        if item.data(0, Qt.UserRole + 1) == "screen":
            run_action = menu.addAction("RUN")
        delete_action = menu.addAction("Delete")
        chosen = menu.exec(self.gui_tree.viewport().mapToGlobal(position))
        if run_action is not None and chosen == run_action:
            self.gui_tree.setCurrentItem(item)
            self.run_gui_screen(item.data(0, Qt.UserRole))
        elif chosen == use_in_create_action:
            self.gui_tree.setCurrentItem(item)
            self.load_gui_node_into_create(item)
        elif chosen == delete_action:
            self.gui_tree.setCurrentItem(item)
            self.delete_gui_node(item.data(0, Qt.UserRole))

    def run_gui_screen(self, node_id=None):
        target_node_id = node_id or (self.gui_tree.currentItem().data(0, Qt.UserRole) if self.gui_tree.currentItem() is not None else None)
        if not target_node_id:
            return None
        kind, _separator, raw_id = str(target_node_id).partition(":")
        screen_id = raw_id or str(target_node_id)
        if kind != "screen":
            return None
        command = [
            sys.executable,
            os.path.abspath(__file__),
            "preview-screen",
            screen_id,
        ]
        subprocess.Popen(command, cwd=PROJECT_DIR)
        self.current_selection.setText(f"Started screen run: {screen_id}")
        return screen_id

    def delete_gui_node(self, node_id=None):
        target_node_id = node_id or (self.gui_tree.currentItem().data(0, Qt.UserRole) if self.gui_tree.currentItem() is not None else None)
        if not target_node_id:
            return None
        kind, _separator, raw_id = str(target_node_id).partition(":")
        entity_id = raw_id or str(target_node_id)
        if kind not in {"screen", "frame", "group"}:
            return None
        expanded_node_ids = self._expanded_gui_node_ids()
        summary = self._collect_gui_delete_summary(kind, entity_id)
        confirmed = QMessageBox.question(
            self,
            "Delete",
            summary,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirmed != QMessageBox.Yes:
            self.current_selection.setText(f"Delete cancelled: {entity_id}")
            return None

        payload = screen_layout_config.load_screen_layout()
        screens = payload.get("screens", {})
        deleted_group_ids = []
        if kind == "group":
            for screen_payload in screens.values():
                groups = screen_payload.get("groups", {})
                if isinstance(groups, dict) and entity_id in groups:
                    groups.pop(entity_id, None)
                    deleted_group_ids.append(entity_id)
        elif kind == "frame":
            screen_id, frame_payload = self._find_screen_for_frame(entity_id, screens)
            if screen_id is None or not isinstance(frame_payload, dict):
                return None
            screen_payload = screens.get(screen_id, {})
            frames = screen_payload.get("frames", {})
            groups = screen_payload.get("groups", {})
            frame_ids_to_delete = self._collect_descendant_frame_ids(entity_id, frames)
            frame_ids_to_delete.add(entity_id)
            if isinstance(groups, dict):
                deleted_group_ids = [
                    group_id
                    for group_id, placement in list(groups.items())
                    if isinstance(placement, dict) and placement.get("frame_id") in frame_ids_to_delete
                ]
                for group_id in deleted_group_ids:
                    groups.pop(group_id, None)
            if isinstance(frames, dict):
                for frame_id in frame_ids_to_delete:
                    frames.pop(frame_id, None)
        else:
            screen_payload = screens.get(entity_id)
            if not isinstance(screen_payload, dict):
                return None
            groups = screen_payload.get("groups", {})
            if isinstance(groups, dict):
                deleted_group_ids = list(groups.keys())
            screens.pop(entity_id, None)
        screen_layout_config.save_screen_layout(payload)

        group_config.reload_group_config()
        for group_id in deleted_group_ids:
            if group_id in group_config.GROUP_CONFIG.get("groups", {}):
                group_config.delete_group(group_id)

        self.reload_explorers()
        self._restore_expanded_gui_node_ids(expanded_node_ids, removed_node_id=target_node_id)
        self._set_gui_delete_status(kind, entity_id)
        return entity_id

    def delete_gui_group(self, node_id=None):
        return self.delete_gui_node(node_id)

    def _collect_gui_delete_summary(self, kind, entity_id):
        layout = screen_layout_config.load_screen_layout()
        screens = layout.get("screens", {})
        if kind == "group":
            return f"Delete group '{entity_id}'?"
        if kind == "frame":
            screen_id, frame_payload = self._find_screen_for_frame(entity_id, screens)
            if screen_id is None or not isinstance(frame_payload, dict):
                return f"Delete frame '{entity_id}'?"
            screen_payload = screens.get(screen_id, {})
            frames = screen_payload.get("frames", {})
            groups = screen_payload.get("groups", {})
            frame_ids_to_delete = self._collect_descendant_frame_ids(entity_id, frames)
            group_count = sum(
                1
                for placement in groups.values()
                if isinstance(placement, dict) and placement.get("frame_id") in frame_ids_to_delete | {entity_id}
            )
            frame_count = len(frame_ids_to_delete) + 1
            return f"Delete frame '{entity_id}' and its {frame_count - 1} child frame(s) with {group_count} group(s)?"
        screen_payload = screens.get(entity_id, {})
        group_count = len(screen_payload.get("groups", {})) if isinstance(screen_payload.get("groups", {}), dict) else 0
        frame_count = len(screen_payload.get("frames", {})) if isinstance(screen_payload.get("frames", {}), dict) else 0
        return f"Delete screen '{entity_id}' with {frame_count} frame(s) and {group_count} group(s)?"

    @staticmethod
    def _collect_descendant_frame_ids(frame_id, frames):
        if not isinstance(frames, dict):
            return set()
        descendants = set()
        queue = [frame_id]
        while queue:
            current_frame_id = queue.pop(0)
            for child_frame_id, child_payload in frames.items():
                if not isinstance(child_payload, dict):
                    continue
                if child_payload.get("parent_frame_id") != current_frame_id or child_frame_id in descendants:
                    continue
                descendants.add(child_frame_id)
                queue.append(child_frame_id)
        return descendants

    def _set_gui_delete_status(self, kind, entity_id):
        message = f"Deleted {kind}: {entity_id}"
        if kind == "screen":
            self.create_status_label.setText(message)
        elif kind == "frame":
            self.create_frame_status_label.setText(message)
        else:
            self.create_group_status_label.setText(message)
        self.current_selection.setText(message)

    def _expanded_gui_node_ids(self):
        if self.gui_tree is None:
            return set()
        expanded = set()
        matches = self.gui_tree.findItems("", Qt.MatchContains | Qt.MatchRecursive, 0)
        for item in matches:
            if item.isExpanded():
                node_id = item.data(0, Qt.UserRole)
                if node_id:
                    expanded.add(node_id)
        return expanded

    def _restore_expanded_gui_node_ids(self, node_ids, removed_node_id=None):
        if self.gui_tree is None:
            return
        removed_node_id = str(removed_node_id or "")
        for node_id in node_ids:
            if removed_node_id and node_id == removed_node_id:
                continue
            item = self._select_gui_node(node_id)
            if item is not None:
                item.setExpanded(True)

    def load_gui_node_into_create(self, item):
        node_id = item.data(0, Qt.UserRole)
        kind = item.data(0, Qt.UserRole + 1)
        context = self._build_gui_create_context(node_id, kind)
        self._clear_create_validation()
        self._reset_group_layer_inputs()
        self.create_screen_id_input.clear()
        self.create_root_frame_id_input.clear()
        self.create_frame_screen_id_input.clear()
        self.create_group_screen_id_input.clear()
        self.create_width_input.clear()
        self.create_height_input.clear()
        self.create_frame_id_input.clear()
        self.create_frame_parent_id_input.clear()
        self.create_frame_x_input.clear()
        self.create_frame_y_input.clear()
        self.create_frame_width_input.clear()
        self.create_frame_height_input.clear()
        self.create_group_id_input.clear()
        self.create_group_frame_id_input.clear()
        self.create_group_x_input.clear()
        self.create_group_y_input.clear()
        if context.get("screen_id"):
            self.create_screen_id_input.setText(context["screen_id"])
            self.create_frame_screen_id_input.setText(context["screen_id"])
            self.create_group_screen_id_input.setText(context["screen_id"])
        if context.get("root_frame_id"):
            self.create_root_frame_id_input.setText(context["root_frame_id"])
        if context.get("screen_size"):
            width, height = context["screen_size"]
            self.create_width_input.setText(str(width))
            self.create_height_input.setText(str(height))
        if context.get("frame_id"):
            self.create_group_frame_id_input.setText(context["frame_id"])
        if kind == "frame":
            self.create_frame_id_input.setText(self._strip_gui_prefix(node_id))
            self.create_frame_parent_id_input.setText(context.get("parent_frame_id", ""))
            rect = context.get("frame_rect")
            if rect:
                self.create_frame_x_input.setText(str(rect[0]))
                self.create_frame_y_input.setText(str(rect[1]))
                self.create_frame_width_input.setText(str(rect[2]))
                self.create_frame_height_input.setText(str(rect[3]))
        elif kind == "group":
            group_id = self._strip_gui_prefix(node_id)
            self.create_group_id_input.setText(group_id)
            placement = context.get("group_placement", {})
            position = placement.get("position", ["", ""])
            self.create_group_x_input.setText(str(position[0]))
            self.create_group_y_input.setText(str(position[1]))
            self._load_group_layers_into_form(context.get("group_payload", {}))
        self.current_selection.setText(f"Loaded into Create: {kind} {self._strip_gui_prefix(node_id)}")

    def _reset_group_layer_inputs(self):
        while len(self.group_graphic_resource_rows) > 1:
            row = self.group_graphic_resource_rows.pop()
            row["widget"].setParent(None)
            row["widget"].deleteLater()
        if self.group_graphic_resource_rows:
            self.group_graphic_resource_rows[0]["entry"].clear()
        self.group_text_value_input.clear()
        self.group_text_font_input.clear()
        self.group_text_size_input.clear()
        self.group_text_color_input.clear()

    def _load_group_layers_into_form(self, group_payload):
        layers = group_payload.get("layers", ()) if isinstance(group_payload, dict) else ()
        graphic_layers = [layer for layer in layers if isinstance(layer, dict) and layer.get("type") != "text" and layer.get("resource_key")]
        text_layer = next((layer for layer in layers if isinstance(layer, dict) and layer.get("type") == "text"), None)
        for index, layer in enumerate(graphic_layers):
            if index == 0 and self.group_graphic_resource_rows:
                target_entry = self.group_graphic_resource_rows[0]["entry"]
            else:
                target_entry = self._append_graphic_resource_row()["entry"]
            target_entry.setText(str(layer.get("resource_key", "")))
        if text_layer is not None:
            self.group_text_value_input.setText(str(text_layer.get("text", "")))
            style = text_layer.get("style", {})
            if isinstance(style, dict):
                self.group_text_font_input.setText(str(style.get("font_name", style.get("font_path", "")) or ""))
                color = style.get("color")
                if isinstance(color, (list, tuple)) and len(color) >= 3:
                    self.group_text_color_input.setText(",".join(str(int(component)) for component in color[:3]))
            size = text_layer.get("size")
            if isinstance(size, (list, tuple)) and len(size) >= 2:
                self.group_text_size_input.setText(f"{size[0]},{size[1]}")

    def _build_gui_create_context(self, node_id, kind):
        stripped_id = self._strip_gui_prefix(node_id)
        layout = screen_layout_config.load_screen_layout()
        screens = layout.get("screens", {})
        groups_payload = group_config.load_group_config().get("groups", {})
        if kind == "screen":
            screen_payload = self._resolve_screen_payload(stripped_id, screens)
            return {
                "screen_id": stripped_id,
                "root_frame_id": screen_payload.get("root_frame_id", ""),
                "screen_size": tuple(screen_payload.get("size", ("", ""))),
            }
        if kind == "frame":
            screen_id, frame_payload = self._find_screen_for_frame(stripped_id, screens)
            if screen_id is None:
                return {}
            screen_payload = self._resolve_screen_payload(screen_id, screens)
            return {
                "screen_id": screen_id,
                "root_frame_id": screen_payload.get("root_frame_id", ""),
                "screen_size": tuple(screen_payload.get("size", ("", ""))),
                "frame_id": frame_payload.get("frame_id", stripped_id),
                "parent_frame_id": frame_payload.get("parent_frame_id", ""),
                "frame_rect": tuple(frame_payload.get("rect", ("", "", "", ""))),
            }
        if kind == "group":
            screen_id, placement = self._find_screen_for_group(stripped_id, screens)
            if screen_id is None:
                return {}
            screen_payload = self._resolve_screen_payload(screen_id, screens)
            return {
                "screen_id": screen_id,
                "root_frame_id": screen_payload.get("root_frame_id", ""),
                "screen_size": tuple(screen_payload.get("size", ("", ""))),
                "frame_id": placement.get("frame_id", ""),
                "group_placement": dict(placement),
                "group_payload": dict(groups_payload.get(stripped_id, {})),
            }
        return {}

    @staticmethod
    def _strip_gui_prefix(node_id):
        return str(node_id).split(":", 1)[-1]

    @staticmethod
    def _resolve_screen_payload(screen_id, screens):
        screen_payload = screens.get(screen_id, {})
        default_payload = screen_layout_config.DEFAULT_SCREEN_LAYOUT.get("screens", {}).get(screen_id, {})
        if not isinstance(screen_payload, dict):
            screen_payload = {}
        if not isinstance(default_payload, dict):
            return screen_payload
        merged_payload = dict(default_payload)
        merged_payload.update(screen_payload)
        return merged_payload

    @staticmethod
    def _find_screen_for_frame(frame_id, screens):
        for screen_id, screen_payload in screens.items():
            frame_payload = screen_payload.get("frames", {}).get(frame_id)
            if isinstance(frame_payload, dict):
                return screen_id, frame_payload
        default_screens = screen_layout_config.DEFAULT_SCREEN_LAYOUT.get("screens", {})
        for screen_id, screen_payload in default_screens.items():
            frame_payload = screen_payload.get("frames", {}).get(frame_id)
            if isinstance(frame_payload, dict):
                return screen_id, dict(frame_payload)
        table_specs = GuiEditorDataService.get_table_screen_frame_specs()
        if frame_id in table_specs:
            frame_payload = dict(table_specs[frame_id])
            manifest_rect = GuiEditorApp._load_gui_manifest_frame_rect(frame_id)
            if manifest_rect is not None:
                frame_payload["rect"] = manifest_rect
            return "table_screen", frame_payload
        return None, None

    @staticmethod
    def _find_screen_for_group(group_id, screens):
        for screen_id, screen_payload in screens.items():
            placement = screen_payload.get("groups", {}).get(group_id)
            if isinstance(placement, dict):
                return screen_id, placement
        return None, None

    @staticmethod
    def _load_gui_manifest_frame_rect(frame_id):
        manifest_path = os.path.join(PROJECT_DIR, "assets", "gui_manifest.json")
        try:
            with open(manifest_path, "r", encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, json.JSONDecodeError):
            return None
        frames = payload.get("frames", {})
        if not isinstance(frames, dict):
            return None
        frame_payload = frames.get(frame_id, {})
        if not isinstance(frame_payload, dict):
            return None
        rect = frame_payload.get("local_rect") or frame_payload.get("rect")
        if not isinstance(rect, (list, tuple)) or len(rect) < 4:
            return None
        return tuple(rect[:4])

    def validate_create_context_from_gui(self, target_kind):
        current_item = self.gui_tree.currentItem()
        if current_item is None:
            QMessageBox.warning(self, "Create context", "Select a GUI Explorer node first")
            return False
        current_kind = current_item.data(0, Qt.UserRole + 1)
        if target_kind == "frame" and current_kind == "group":
            QMessageBox.warning(self, "Create context", "Cannot create a frame from a group context")
            self._mark_invalid_fields(self.create_frame_parent_id_input)
            return False
        if target_kind == "group" and current_kind == "screen" and not self.create_group_frame_id_input.text().strip():
            QMessageBox.warning(self, "Create context", "Cannot create a group from a screen context without a frame")
            self._mark_invalid_fields(self.create_group_frame_id_input)
            return False
        return True

    def _mark_invalid_fields(self, *widgets):
        for widget in widgets:
            if widget is None:
                continue
            if self._default_line_edit_style is None:
                self._default_line_edit_style = widget.styleSheet()
            widget.setStyleSheet("border: 1px solid #d9534f; background: #3a2626;")

    def _clear_create_validation(self):
        for widget in (
            self.create_screen_id_input,
            self.create_root_frame_id_input,
            self.create_width_input,
            self.create_height_input,
            self.create_frame_screen_id_input,
            self.create_frame_id_input,
            self.create_frame_parent_id_input,
            self.create_frame_x_input,
            self.create_frame_y_input,
            self.create_frame_width_input,
            self.create_frame_height_input,
            self.create_group_screen_id_input,
            self.create_group_id_input,
            self.create_group_frame_id_input,
            self.create_group_x_input,
            self.create_group_y_input,
        ):
            if widget is not None:
                widget.setStyleSheet(self._default_line_edit_style or "")

    def _collect_screen_geometry_conflicts(self, screen_id, root_frame_id, size):
        layout = screen_layout_config.load_screen_layout()
        screen_payload = layout.get("screens", {}).get(screen_id)
        if not isinstance(screen_payload, dict):
            return []
        current_size = tuple(screen_payload.get("size", ()))
        current_root_frame_id = screen_payload.get("root_frame_id")
        size_changed = current_size != (int(size[0]), int(size[1]))
        root_changed = current_root_frame_id != str(root_frame_id)
        if not size_changed and not root_changed:
            return []
        blocking_nodes = [f"screen:{screen_id}"]
        for frame_id in screen_payload.get("frames", {}):
            blocking_nodes.append(f"frame:{frame_id}")
        for group_id in screen_payload.get("groups", {}):
            blocking_nodes.append(f"group:{group_id}")
        return blocking_nodes

    def _collect_frame_geometry_conflicts(self, screen_id, frame_id, rect):
        layout = screen_layout_config.load_screen_layout()
        screen_payload = layout.get("screens", {}).get(screen_id, {})
        frames = screen_payload.get("frames", {})
        existing_frame = frames.get(frame_id)
        if not isinstance(existing_frame, dict):
            return []
        current_rect = tuple(existing_frame.get("rect", ()))
        if current_rect == tuple(int(value) for value in rect):
            return []
        child_frames = [
            child_frame_id
            for child_frame_id, child_payload in frames.items()
            if isinstance(child_payload, dict) and child_payload.get("parent_frame_id") == frame_id
        ]
        child_groups = [
            group_id
            for group_id, placement in screen_payload.get("groups", {}).items()
            if isinstance(placement, dict) and placement.get("frame_id") == frame_id
        ]
        if not child_frames and not child_groups:
            return []
        blocking_nodes = [f"frame:{frame_id}"]
        blocking_nodes.extend(f"frame:{child_frame_id}" for child_frame_id in child_frames)
        blocking_nodes.extend(f"group:{group_id}" for group_id in child_groups)
        return blocking_nodes

    def _show_gui_geometry_conflicts(self, node_ids, message):
        self.gui_problem_node_ids = set(node_ids)
        self.populate_gui_tree()
        for node_id in node_ids:
            self._select_gui_node(node_id, expand_parents=True)
        self.right_tabs.setCurrentIndex(1)
        QMessageBox.warning(self, "Geometry save blocked", message)

    def _apply_theme(self, theme_name):
        self.theme_name = theme_name
        for value, action in self.theme_actions.items():
            action.setChecked(value == theme_name)
        branch_assets = self._branch_asset_urls()
        if theme_name == "darkly":
            accent = "#375a7f"
            panel = "#22252a"
            panel_alt = "#2f3136"
        else:
            accent = "#2a9fd6"
            panel = "#1f2b38"
            panel_alt = "#2c3e50"
        self.setStyleSheet(
            f"""
            QMainWindow, QWidget {{
                background: #1e1f22;
                color: #e8e8e8;
            }}
            QFrame {{
                background: {panel};
            }}
            QFrame[panel="true"] {{
                background: {panel};
                border: 1px solid #3c4148;
            }}
            QLabel[role="title"] {{
                font-weight: 700;
            }}
            QLabel[role="muted"] {{
                color: #aeb4bf;
            }}
            QPushButton, QComboBox, QLineEdit {{
                background: {panel_alt};
                border: 1px solid #3c4148;
                padding: 1px 6px;
            }}
            QTabWidget::pane {{
                border: 0;
                background: {panel};
            }}
            QTabBar::tab {{
                background: {panel_alt};
                color: #e8e8e8;
                padding: 6px 10px;
                margin-right: 4px;
            }}
            QTabBar::tab:selected {{
                background: {accent};
            }}
            QTreeWidget {{
                background: #17181b;
                border: 1px solid #3c4148;
                alternate-background-color: #1d1f24;
                outline: 0;
            }}
            QTreeWidget::item {{
                padding: 3px 0;
            }}
            QTreeWidget::item:selected {{
                background: {accent};
                color: #ffffff;
            }}
            QTreeView::branch:has-siblings:!adjoins-item {{
                border-image: url({branch_assets["vline"]}) 0;
            }}
            QTreeView::branch:has-siblings:adjoins-item {{
                border-image: url({branch_assets["more"]}) 0;
            }}
            QTreeView::branch:!has-children:!has-siblings:adjoins-item {{
                border-image: url({branch_assets["end"]}) 0;
            }}
            QTreeView::branch:has-children:!has-siblings:closed,
            QTreeView::branch:closed:has-children:has-siblings {{
                border-image: none;
                image: url({branch_assets["closed"]});
            }}
            QTreeView::branch:open:has-children:!has-siblings,
            QTreeView::branch:open:has-children:has-siblings {{
                border-image: none;
                image: url({branch_assets["open"]});
            }}
            QHeaderView::section {{
                background: {panel_alt};
                color: #e8e8e8;
                border: 0;
                padding: 6px;
                font-weight: 700;
            }}
            """
        )
        for tree in (self.rm_tree, self.gui_tree):
            if tree is not None:
                tree.setAlternatingRowColors(True)
                tree.style().unpolish(tree)
                tree.style().polish(tree)

    @staticmethod
    def _branch_asset_urls():
        return {
            "vline": GuiEditorApp._style_url("branch_vline.png"),
            "more": GuiEditorApp._style_url("branch_more.png"),
            "end": GuiEditorApp._style_url("branch_end.png"),
            "closed": GuiEditorApp._style_url("branch_closed.png"),
            "open": GuiEditorApp._style_url("branch_open.png"),
        }

    @staticmethod
    def _style_url(filename):
        normalized = os.path.join(GUI_EDITOR_ASSETS_DIR, filename).replace("\\", "/")
        return normalized

    @staticmethod
    def _title_label(text):
        label = QLabel(text)
        label.setProperty("role", "title")
        return label

    @staticmethod
    def _muted_label(text):
        label = QLabel(text)
        label.setProperty("role", "muted")
        return label


def build_parser():
    parser = argparse.ArgumentParser(prog="gui_editor.py", add_help=True)
    subparsers = parser.add_subparsers(dest="command")

    preview_parser = subparsers.add_parser("preview-screen", help="Launch a static screen preview.")
    preview_parser.add_argument("screen_id")

    return parser


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "preview-screen":
        screen_id = str(args.screen_id or "").strip()
        if screen_id == "table_screen":
            return run_table_screen_gui_preview()
        return run_layout_screen_preview(screen_id)

    app = QApplication.instance() or QApplication(sys.argv)
    window = GuiEditorApp()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
