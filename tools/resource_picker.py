"""Dev utility for PNG resources, PNG frame metadata, and derived manifests."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
import json
import os
import re
import sys
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk
from tkinter import font as tkfont

from PIL import Image, ImageDraw, ImageFont, ImageTk
from PIL.PngImagePlugin import PngInfo

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from core.resource import ResourceManager  # noqa: E402
from core import GameController  # noqa: E402
from group import GroupStore  # noqa: E402
from screens.table_screen import TableScreen  # noqa: E402
import group_config  # noqa: E402


FRAME_WIDTH_KEY = "frame_width"
FRAME_HEIGHT_KEY = "frame_height"
GUI_MANIFEST_FILE_NAME = "gui_manifest.json"


@dataclass(frozen=True)
class PngMetadata:
    frame_width: int | None
    frame_height: int | None
    warnings: tuple[str, ...] = ()

    @property
    def has_frame_size(self):
        return self.frame_width is not None and self.frame_height is not None


@dataclass(frozen=True)
class PngAsset:
    path: str
    relative_path: str
    file_name: str
    resource_key: str
    size: tuple[int, int]
    metadata: PngMetadata

    @property
    def manifest_frame_size(self):
        if self.metadata.has_frame_size and not self.metadata.warnings:
            return self.metadata.frame_width, self.metadata.frame_height
        return self.size


@dataclass(frozen=True)
class GraphicEntry:
    group_module: str
    group_file: str
    local_name: str
    resource_key: str
    position: tuple[int, int]
    asset: PngAsset | None
    status: str
    warnings: tuple[str, ...] = ()

    @property
    def display_name(self):
        return f"({self.local_name!r}, {self.resource_key!r}, {self.position!r})"


@dataclass
class OperationReport:
    title: str
    lines: list[str] = field(default_factory=list)

    def add(self, text=""):
        self.lines.append(str(text))

    def extend(self, values):
        self.lines.extend(str(value) for value in values)

    def to_text(self):
        if not self.lines:
            return self.title
        return "\n".join([self.title, "", *self.lines])


class PlaceholderResourceManager:
    """Resource manager facade for GuiManifest builds without a pygame display."""

    _records = {}
    _frames = {}
    _assets_dir = None

    @classmethod
    def build_index(cls, assets_dir):
        cls._assets_dir = os.path.abspath(assets_dir)
        cls._frames = {}
        cls._records = ResourceManager.build_index(cls._assets_dir)
        return cls._records

    @classmethod
    def get_frames(cls, key_or_path):
        import pygame

        key = ResourceManager.resolve_resource_key(key_or_path)
        if key in cls._frames:
            return cls._frames[key]

        record = cls.get_or_create_record(key)
        surface = pygame.Surface(record.frame_size, pygame.SRCALPHA)
        cls._frames[key] = [surface for _index in ResourceManager.get_frame_grid(record)]
        return cls._frames[key]

    @classmethod
    def get_or_create_record(cls, resource_key):
        if resource_key in cls._records:
            return cls._records[resource_key]

        file_path = ResourceManager.find_asset_path_for_key(resource_key)
        if file_path is None:
            raise KeyError(f"PNG not found for GuiManifest resource layer: {resource_key}")

        entry = ResourceManager.create_default_manifest_entry(file_path, cls._assets_dir)
        record = ResourceManager.create_record(resource_key, entry, cls._assets_dir)
        cls._records[resource_key] = record
        return record


class ResourcePickerService:
    """Non-Tkinter services used by ResourcePickerApp."""

    def __init__(self, project_dir, assets_dir):
        self.project_dir = os.path.abspath(project_dir)
        self.assets_dir = os.path.abspath(assets_dir)

    def load_png_assets(self):
        assets = []
        for file_path in ResourceManager.get_png_files(self.assets_dir):
            relative_path = os.path.relpath(file_path, self.assets_dir).replace("\\", "/")
            with Image.open(file_path) as image:
                size = image.size
            metadata = self.read_png_metadata(file_path, size)
            assets.append(
                PngAsset(
                    path=os.path.abspath(file_path),
                    relative_path=relative_path,
                    file_name=os.path.basename(file_path),
                    resource_key=ResourceManager.build_resource_key(relative_path),
                    size=size,
                    metadata=metadata,
                )
            )
        return sorted(assets, key=lambda item: item.relative_path.lower())

    def load_graphics_entries(self, assets_by_key=None, manifest=None):
        assets_by_key = assets_by_key or {asset.resource_key: asset for asset in self.load_png_assets()}
        manifest_resources = (manifest or {}).get("resources", {})
        entries = []
        group_config.reload_group_config()
        for group_id in group_config.iter_group_ids():
            config = group_config.get_group_config(group_id)
            for local_name, resource_key, position in self.iter_group_config_layers(config.get("layers", ())):
                asset = assets_by_key.get(resource_key)
                warnings = []
                if asset is None:
                    status = "missing PNG"
                    warnings.append(f"PNG not found for resource_key: {resource_key}")
                elif resource_key not in manifest_resources:
                    status = "missing manifest"
                elif asset.metadata.warnings:
                    status = "metadata warning"
                    warnings.extend(asset.metadata.warnings)
                else:
                    status = "OK"

                entries.append(
                    GraphicEntry(
                        group_module="group_config",
                        group_file=group_id,
                        local_name=local_name,
                        resource_key=resource_key,
                        position=position,
                        asset=asset,
                        status=status,
                        warnings=tuple(warnings),
                    )
                )
        return entries

    @staticmethod
    def iter_group_config_layers(layers):
        for layer in layers:
            if layer.get("type", "image") != "image":
                continue
            local_name = layer.get("name")
            resource_key = layer.get("resource_key")
            position = layer.get("position", (0, 0))
            if local_name and resource_key:
                yield str(local_name), str(resource_key), ResourcePickerService.normalize_layer_position(position)

    @staticmethod
    def iter_graphics(graphics):
        for item in graphics:
            if isinstance(item, dict):
                local_name = item.get("name") or item.get("layer_name") or item.get("local_name")
                resource_key = item.get("resource_key")
                position = item.get("position", item.get("local_position", (0, 0)))
            elif isinstance(item, (tuple, list)) and len(item) >= 2:
                local_name, resource_key = item[0], item[1]
                position = item[2] if len(item) >= 3 else (0, 0)
            else:
                continue

            if local_name and resource_key:
                yield str(local_name), str(resource_key), ResourcePickerService.normalize_layer_position(position)

    @staticmethod
    def normalize_layer_position(position):
        if position is None:
            return (0, 0)
        if isinstance(position, dict):
            return (int(position.get("x", 0)), int(position.get("y", 0)))
        if isinstance(position, (tuple, list)) and len(position) >= 2:
            return (int(position[0]), int(position[1]))
        return (0, 0)

    @staticmethod
    def read_png_metadata(file_path, image_size=None):
        warnings = []
        with Image.open(file_path) as image:
            info = dict(image.info)
            image_size = image_size or image.size

        frame_width = ResourcePickerService.parse_optional_int(info.get(FRAME_WIDTH_KEY))
        frame_height = ResourcePickerService.parse_optional_int(info.get(FRAME_HEIGHT_KEY))
        image_width, image_height = image_size

        if frame_width is None or frame_height is None:
            warnings.append("PNG metadata is missing frame_width/frame_height")
        else:
            if frame_width <= 0:
                warnings.append("frame_width must be > 0")
            if frame_height <= 0:
                warnings.append("frame_height must be > 0")
            if frame_width != image_width:
                warnings.append("current slicer supports one column: frame_width must match PNG width")
            if frame_height and frame_height > 0 and image_height % frame_height != 0:
                warnings.append("PNG height must be divisible by frame_height")

        return PngMetadata(frame_width, frame_height, tuple(warnings))

    @staticmethod
    def write_png_metadata(file_path, frame_width, frame_height):
        with Image.open(file_path) as image:
            image_width, image_height = image.size
            if frame_width != image_width:
                raise ValueError("current slicer supports one column: frame_width must match PNG width")
            if frame_width <= 0 or frame_height <= 0:
                raise ValueError("frame_width and frame_height must be > 0")
            if image_height % frame_height != 0:
                raise ValueError("PNG height must be divisible by frame_height")

            png_info = PngInfo()
            for key, value in image.info.items():
                if key in (FRAME_WIDTH_KEY, FRAME_HEIGHT_KEY):
                    continue
                if isinstance(value, str):
                    png_info.add_text(key, value)
            png_info.add_text(FRAME_WIDTH_KEY, str(frame_width))
            png_info.add_text(FRAME_HEIGHT_KEY, str(frame_height))
            image.save(file_path, pnginfo=png_info)

    @staticmethod
    def parse_optional_int(value):
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def build_manifest_from_graphics(self):
        assets = self.load_png_assets()
        assets_by_key = {asset.resource_key: asset for asset in assets}
        entries = self.load_graphics_entries(assets_by_key=assets_by_key, manifest={"resources": {}})
        resources = {}
        report = OperationReport("Build RM Manifest")
        missing_png = []
        metadata_warnings = []

        for entry in entries:
            if entry.asset is None:
                missing_png.append(f"{entry.group_file}: {entry.resource_key}")
                continue

            frame_width, frame_height = entry.asset.manifest_frame_size
            if entry.asset.metadata.warnings:
                metadata_warnings.append(
                    f"{entry.resource_key}: {'; '.join(entry.asset.metadata.warnings)}; "
                    f"manifest uses safe full-image frame {frame_width}x{frame_height}"
                )

            resources[entry.resource_key] = {
                "path": entry.asset.relative_path,
                "frame_width": frame_width,
                "frame_height": frame_height,
            }

        manifest = ResourceManager.normalize_manifest({"resources": resources})
        report.add(f"Resources written: {len(resources)}")
        report.add(f"Missing PNG: {len(missing_png)}")
        report.add(f"Metadata warnings: {len(metadata_warnings)}")
        if missing_png:
            report.add("")
            report.add("Missing PNG:")
            report.extend(missing_png)
        if metadata_warnings:
            report.add("")
            report.add("Metadata warnings:")
            report.extend(metadata_warnings)
        return manifest, report

    def upsert_group_config_image_layer(
        self,
        group_id,
        layer_name,
        resource_key,
        position=(0, 0),
        role="",
        target_id="",
    ):
        """Create or update a group_config image layer from an RM Manifest resource key."""
        group_metadata = {}
        if role:
            group_metadata["role"] = role
        layer = group_config.upsert_image_layer(
            group_id,
            layer_name,
            resource_key,
            position=position,
            group_metadata=group_metadata,
        )
        target = None
        if target_id:
            target = group_config.upsert_manifest_target(
                group_id,
                target_id,
                "resource",
                layer_name,
                description=f"{group_id}.{layer_name}",
            )

        report = OperationReport("Group Config Update")
        report.add(f"group: {group_id}")
        report.add(f"layer: {layer_name}")
        report.add(f"resource_key: {resource_key}")
        report.add(f"position: {tuple(position)}")
        if role:
            report.add(f"role: {role}")
        if target_id:
            report.add(f"target: {target_id} -> {target}")
        report.add("")
        report.add(f"Saved: {group_config.GROUP_CONFIG_FILE}")
        return layer, report

    def set_group_config_layer_position(self, group_id, layer_name, position):
        layer = group_config.set_layer_position(group_id, layer_name, position)
        report = OperationReport("Group Config Layer Position")
        report.add(f"group: {group_id}")
        report.add(f"layer: {layer_name}")
        report.add(f"position: {tuple(position)}")
        report.add("")
        report.add(f"Saved: {group_config.GROUP_CONFIG_FILE}")
        return layer, report

    def set_group_config_text_layer(self, group_id, layer_name, updates):
        layer = group_config.set_text_layer_config(group_id, layer_name, updates)
        report = OperationReport("Group Config Text Layer")
        report.add(f"group: {group_id}")
        report.add(f"layer: {layer_name}")
        report.add(f"text: {layer.get('text', '')}")
        report.add(f"size: {tuple(layer.get('size', ())) if layer.get('size') else None}")
        report.add(f"fit_mode: {layer.get('fit_mode', 'none')}")
        report.add(f"style: {layer.get('style', {})}")
        report.add("")
        report.add(f"Saved: {group_config.GROUP_CONFIG_FILE}")
        return layer, report

    def save_group_config_metadata(self, group_id, metadata, source_group_id=None):
        group = group_config.upsert_group(group_id, metadata, source_group_id=source_group_id)
        report = OperationReport("Group Config Metadata")
        report.add(f"group: {group_id}")
        report.add(f"source_group: {source_group_id or group_id}")
        report.add(f"rect: {group.get('rect')}")
        report.add(f"hit_rect: {group.get('hit_rect')}")
        report.add(f"scale_factor: {group.get('scale_factor')}")
        report.add(f"layers: {len(group.get('layers', ())) }")
        report.add("")
        report.add(f"Saved: {group_config.GROUP_CONFIG_FILE}")
        return group, report

    def delete_group_config_layer(self, group_id, layer_name):
        removed = group_config.delete_layer(group_id, layer_name)
        report = OperationReport("Group Config Layer Delete")
        report.add(f"group: {group_id}")
        report.add(f"layer: {layer_name}")
        report.add(f"removed: {removed}")
        report.add("")
        report.add(f"Saved: {group_config.GROUP_CONFIG_FILE}")
        return removed, report

    def add_png_asset_to_manifest(self, asset):
        manifest = self.load_manifest_if_exists()
        resources = manifest.setdefault("resources", {})
        resources[asset.resource_key] = ResourceManager.create_default_manifest_entry(asset.path, self.assets_dir)
        saved_manifest = ResourceManager.save_manifest(self.assets_dir, manifest)
        report = OperationReport("Add to RM Manifest")
        report.add(f"resource_key: {asset.resource_key}")
        report.add(f"path: {asset.relative_path}")
        report.add(f"resources: {len(saved_manifest.get('resources', {}))}")
        return saved_manifest, report

    def update_manifest_from_graphics(self):
        old_manifest = self.load_manifest_if_exists()
        old_resources = old_manifest.get("resources", {})
        new_manifest, report = self.build_manifest_from_graphics()
        new_resources = new_manifest.get("resources", {})

        old_keys = set(old_resources)
        new_keys = set(new_resources)
        added = sorted(new_keys - old_keys)
        removed = sorted(old_keys - new_keys)
        changed = sorted(
            key
            for key in old_keys & new_keys
            if old_resources.get(key) != new_resources.get(key)
        )

        update_report = OperationReport("RM Manifest Update")
        update_report.add(f"Resources after update: {len(new_resources)}")
        update_report.add(f"Added: {len(added)}")
        update_report.add(f"Removed: {len(removed)}")
        update_report.add(f"Changed: {len(changed)}")
        update_report.add("")
        update_report.add(report.to_text())
        if added:
            update_report.add("")
            update_report.add("Added:")
            update_report.extend(added)
        if removed:
            update_report.add("")
            update_report.add("Removed:")
            update_report.extend(removed)
        if changed:
            update_report.add("")
            update_report.add("Changed:")
            update_report.extend(changed)
        return new_manifest, update_report

    def build_groups_from_config(self):
        group_config.reload_group_config()
        payload = group_config.load_group_config()
        groups = payload.get("groups", {})
        groups_store_dir = os.path.join(PROJECT_DIR, "groups_store")
        os.makedirs(groups_store_dir, exist_ok=True)

        init_path = os.path.join(groups_store_dir, "__init__.py")
        if not os.path.exists(init_path):
            with open(init_path, "w", encoding="utf-8") as file:
                file.write('"""Generated group builders."""\n')

        written = []
        unchanged = []
        module_paths = []
        for group_id in sorted(groups):
            group_name = re.sub(r"\W+", "_", group_id).strip("_").lower()
            if not group_name:
                group_name = "group"
            if group_name[0].isdigit():
                group_name = f"group_{group_name}"
            module_name = group_name if group_name.endswith("_group") else f"{group_name}_group"
            module_paths.append(f"groups_store.{module_name}")
            file_path = os.path.join(groups_store_dir, f"{module_name}.py")
            content = (
                '"""Build this group from group_config.json."""\n\n'
                "from group import Group\n\n\n"
                f"GROUP_ID = {group_id!r}\n\n\n"
                "def create(resource_manager):\n"
                "    return Group.from_config(GROUP_ID, resource_manager)\n"
            )
            old_content = None
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as file:
                    old_content = file.read()
            if old_content == content:
                unchanged.append(file_path)
                continue
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(content)
            written.append(file_path)

        PlaceholderResourceManager.build_index(self.assets_dir)
        group_store = GroupStore(resource_manager=PlaceholderResourceManager)
        group_store.build()

        report = OperationReport("Build Groups")
        report.add(f"Groups in group_config.json: {len(groups)}")
        report.add(f"Groups built by GroupStore: {len(group_store)}")
        report.add(f"Builder files written: {len(written)}")
        report.add(f"Builder files unchanged: {len(unchanged)}")
        report.add("group_store.py source: group_config.iter_group_ids()")
        if module_paths:
            report.add("")
            report.add("Builder modules:")
            report.extend(module_paths)
        return group_store, report

    def get_gui_manifest_path(self):
        return os.path.join(self.assets_dir, GUI_MANIFEST_FILE_NAME)

    def load_gui_manifest_if_exists(self):
        manifest_path = self.get_gui_manifest_path()
        if not os.path.exists(manifest_path):
            return self.empty_gui_manifest()
        with open(manifest_path, "r", encoding="utf-8") as file:
            return json.load(file)

    def save_gui_manifest(self, manifest):
        manifest_path = self.get_gui_manifest_path()
        with open(manifest_path, "w", encoding="utf-8") as file:
            json.dump(manifest, file, ensure_ascii=False, indent=2)
            file.write("\n")

    @staticmethod
    def empty_gui_manifest():
        return {
            "version": 1,
            "screens": {},
            "frames": {},
            "groups": {},
            "hierarchy": {},
        }

    def build_gui_manifest(self):
        PlaceholderResourceManager.build_index(self.assets_dir)
        group_store = GroupStore(resource_manager=PlaceholderResourceManager)
        group_store.build()
        screen = TableScreen(
            group_store=group_store,
            game_controller=GameController(GameController.create_fixture_state()),
        )

        manifest = self.create_gui_manifest_from_screen("table_screen", screen, group_store)
        report = OperationReport("Build GuiManifest")
        report.add(f"Screens: {len(manifest['screens'])}")
        report.add(f"Frames: {len(manifest['frames'])}")
        report.add(f"Groups: {len(manifest['groups'])}")
        report.add(
            "Layers: "
            f"{sum(len(group.get('layers', {})) for group in manifest['groups'].values())}"
        )
        return manifest, report

    def update_gui_manifest(self):
        old_manifest = self.load_gui_manifest_if_exists()
        new_manifest, report = self.build_gui_manifest()

        old_objects = self.collect_gui_object_ids(old_manifest)
        new_objects = self.collect_gui_object_ids(new_manifest)
        added = sorted(new_objects - old_objects)
        removed = sorted(old_objects - new_objects)

        update_report = OperationReport("GuiManifest Update")
        update_report.add(report.to_text())
        update_report.add("")
        update_report.add(f"Added objects: {len(added)}")
        update_report.add(f"Removed objects: {len(removed)}")
        if added:
            update_report.add("")
            update_report.add("Added:")
            update_report.extend(added)
        if removed:
            update_report.add("")
            update_report.add("Removed:")
            update_report.extend(removed)
        return new_manifest, update_report

    @staticmethod
    def collect_gui_object_ids(manifest):
        object_ids = set()
        for screen_id in manifest.get("screens", {}):
            object_ids.add(f"screen:{screen_id}")
        for frame_id in manifest.get("frames", {}):
            object_ids.add(f"frame:{frame_id}")
        for group_id, group in manifest.get("groups", {}).items():
            object_ids.add(f"group:{group_id}")
            for layer_id in group.get("layers", {}):
                object_ids.add(f"layer:{group_id}.{layer_id}")
        return object_ids

    def create_gui_manifest_from_screen(self, screen_id, screen, group_store):
        frames = {
            frame_id: self.create_frame_manifest_entry(frame)
            for frame_id, frame in sorted(screen.screen_frames.items())
        }
        group_locations = self.collect_group_locations(frames)
        groups = {
            group_id: self.create_group_manifest_entry(group_store.get(group_id), group_locations)
            for group_id in group_store.all_ids()
        }
        root_frame_ids = [
            frame.id
            for frame in screen.iter_root_frames()
        ]
        return {
            "version": 1,
            "screens": {
                screen_id: {
                    "id": screen_id,
                    "class": f"{screen.__class__.__module__}.{screen.__class__.__name__}",
                    "background_color": list(screen.background_color),
                    "root_frame_ids": root_frame_ids,
                    "active_group_ids": list(screen.active_group_ids),
                }
            },
            "frames": frames,
            "groups": groups,
            "hierarchy": {
                screen_id: {
                    "root_frame_ids": root_frame_ids,
                    "active_group_ids": list(screen.active_group_ids),
                }
            },
        }

    @staticmethod
    def create_frame_manifest_entry(frame):
        payload = frame.to_payload()
        return {
            "id": payload["frame_id"],
            "parent_frame_id": payload["parent_frame_id"],
            "local_rect": list(payload["local_rect"]),
            "rect": list(payload["rect"]),
            "hit_rect": list(payload["hit_rect"]),
            "group_ids": list(payload["group_ids"]),
            "child_frame_ids": list(payload["child_frame_ids"]),
            "group_origins": {
                group_id: list(position)
                for group_id, position in payload["group_origins"].items()
            },
            "action_count": payload["action_count"],
            "padding": payload["padding"],
            "spacing": payload["spacing"],
        }

    @staticmethod
    def collect_group_locations(frames):
        locations = {}
        for frame_id, frame in frames.items():
            for group_id in frame.get("group_ids", ()):
                locations.setdefault(group_id, []).append(frame_id)
        return locations

    @staticmethod
    def create_group_manifest_entry(group, group_locations):
        payload = group.to_manifest_entry()
        payload["frame_ids"] = group_locations.get(group.id, [])
        return payload

    @staticmethod
    def format_gui_object_details(object_type, object_id, payload):
        lines = [
            f"Type: {object_type}",
            f"ID: {object_id}",
            "",
            json.dumps(payload, ensure_ascii=False, indent=2),
        ]
        return "\n".join(lines)

    def load_manifest_if_exists(self):
        manifest_path = ResourceManager.get_manifest_path(self.assets_dir)
        if not os.path.exists(manifest_path):
            return {"resources": {}}
        return ResourceManager.load_manifest(self.assets_dir)

    @staticmethod
    def create_graphics_snippet(asset):
        local_name = ResourcePickerService.create_local_name_from_file(asset.file_name)
        return "\n".join(
            [
                "{",
                f"  \"name\": {local_name!r},",
                "  \"type\": \"image\",",
                f"  \"resource_key\": {asset.resource_key!r},",
                "  \"position\": [0, 0]",
                "}",
            ]
        )

    @staticmethod
    def create_local_name_from_file(file_name):
        name, _ext = os.path.splitext(file_name)
        return re.sub(r"\W+", "_", name.strip()).strip("_") or "resource"

    @staticmethod
    def load_available_fonts():
        fonts_dir = os.path.join(PROJECT_DIR, "assets", "fonts")
        fonts = []
        for root_dir, _dirs, file_names in os.walk(fonts_dir):
            for file_name in sorted(file_names):
                if not file_name.lower().endswith((".ttf", ".otf")):
                    continue
                file_path = os.path.join(root_dir, file_name)
                fonts.append(os.path.relpath(file_path, PROJECT_DIR).replace("\\", "/"))
        return fonts


class ResourcePickerApp:
    """Tkinter shell for resource picker workflows."""

    WINDOW_SIZE = "1040x1000+0+0"
    PREVIEW_SIZE = (560, 380)
    COLORS = {
        "app_bg": "#1e1e1e",
        "panel_bg": "#252526",
        "card_bg": "#2d2d30",
        "field_bg": "#323236",
        "field_bg_active": "#3a3a40",
        "preview_bg": "#181818",
        "zone_bg": "#2b2b31",
        "zone_border": "#565664",
        "zone_highlight": "#323238",
        "text": "#f0f0f0",
        "muted_text": "#b8b8b8",
        "heading": "#ffffff",
        "border": "#3f3f46",
        "accent": "#007acc",
        "accent_active": "#1594e8",
        "danger": "#c75050",
    }

    def __init__(self, root, assets_dir):
        self.root = root
        self.assets_dir = os.path.abspath(assets_dir)
        self.service = ResourcePickerService(PROJECT_DIR, self.assets_dir)
        self.manifest = {"resources": {}}
        self.gui_manifest = self.service.load_gui_manifest_if_exists()
        self.rm_manifest_loaded = False
        self.png_assets = []
        self.png_assets_by_key = {}
        self.visible_png_assets = []
        self.graphics_entries = []
        self.visible_graphics_entries = []
        self.png_assets_by_item = {}
        self.group_config_nav_by_item = {}
        self.gui_manifest_nav_by_item = {}
        self.group_editor_layer_by_item = {}
        self.is_populating_group_editor_layers = False
        self.png_folder_items = {}
        self.rm_resource_by_item = {}
        self.png_rm_resource_by_item = {}
        self.preview_image = None
        self.preview_asset = None
        self.selected_asset = None
        self.selected_graphic = None
        self.selected_manifest_resource_key = None
        self.group_edit_source_id = None
        self.preview_after_id = None
        self.group_builder_sections = {}
        self.edit_group_active = False
        self.edit_group_id = ""
        self.details_output_hidden = True

        self.resource_key_var = tk.StringVar()
        self.path_var = tk.StringVar()
        self.png_size_var = tk.StringVar()
        self.frame_width_var = tk.StringVar()
        self.frame_height_var = tk.StringVar()
        self.details_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self.right_title_var = tk.StringVar(value="PNG Workbench")
        self.group_mode_var = tk.StringVar(value="Mode: Create")
        self.layer_type_var = tk.StringVar(value="Graphic")
        self.search_var = tk.StringVar()
        self.result_var = tk.StringVar()
        self.group_id_var = tk.StringVar()
        self.group_tags_var = tk.StringVar()
        self.group_rect_x_var = tk.StringVar(value="0")
        self.group_rect_y_var = tk.StringVar(value="0")
        self.group_rect_w_var = tk.StringVar(value="0")
        self.group_rect_h_var = tk.StringVar(value="0")
        self.group_hit_x_var = tk.StringVar(value="0")
        self.group_hit_y_var = tk.StringVar(value="0")
        self.group_hit_w_var = tk.StringVar(value="0")
        self.group_hit_h_var = tk.StringVar(value="0")
        self.group_scale_var = tk.StringVar(value="1.0")
        self.group_hide_rect_var = tk.BooleanVar(value=True)
        self.layer_name_var = tk.StringVar()
        self.graphic_layer_choice_var = tk.StringVar()
        self.text_layer_choice_var = tk.StringVar()
        self.layer_x_var = tk.StringVar(value="0")
        self.layer_y_var = tk.StringVar(value="0")
        self.group_role_var = tk.StringVar()
        self.target_id_var = tk.StringVar()
        self.graphic_resource_key_var = tk.StringVar()
        self.graphic_resource_full_key = ""
        self.text_value_var = tk.StringVar()
        self.text_key_var = tk.StringVar()
        self.text_width_var = tk.StringVar(value="0")
        self.text_height_var = tk.StringVar(value="0")
        self.text_fit_mode_var = tk.StringVar(value="none")
        self.font_name_var = tk.StringVar()
        self.font_path_var = tk.StringVar()
        self.font_size_var = tk.StringVar(value="24")
        self.font_color_hex_var = tk.StringVar(value="#ffffff")
        self.layer_scale_w_var = tk.StringVar(value="100")
        self.layer_scale_h_var = tk.StringVar(value="100")
        self.font_color_r_var = tk.StringVar(value="255")
        self.font_color_g_var = tk.StringVar(value="255")
        self.font_color_b_var = tk.StringVar(value="255")
        self.font_antialias_var = tk.BooleanVar(value=True)
        self.available_fonts = ResourcePickerService.load_available_fonts()

        self.configure_window()
        self.create_widgets()
        self.trace_create_group_preview_vars()
        self.search_var.trace_add("write", self.on_search)
        self.reload_index()

    def configure_window(self):
        self.root.title("Resource Picker")
        self.root.geometry(self.WINDOW_SIZE)
        self.root.minsize(980, 1000)
        self.root.maxsize(self.root.winfo_screenwidth(), 1000)
        self.root.resizable(True, False)
        colors = self.COLORS
        self.root.configure(bg=colors["app_bg"])
        self.configure_fonts()

        style = ttk.Style(self.root)
        self.apply_external_theme(style)
        style.configure(
            ".",
            background=colors["app_bg"],
            foreground=colors["text"],
            fieldbackground=colors["field_bg"],
            bordercolor=colors["border"],
            lightcolor=colors["border"],
            darkcolor=colors["border"],
            font=("Segoe UI", 10),
        )
        style.configure("TFrame", background=colors["app_bg"])
        style.configure("Card.TFrame", background=colors["card_bg"])
        style.configure("Panel.TFrame", background=colors["panel_bg"])
        style.configure("Zone.TFrame", background=colors["zone_bg"])
        style.configure("TLabel", background=colors["app_bg"], foreground=colors["text"])
        style.configure("Card.TLabel", background=colors["card_bg"], foreground=colors["text"])
        style.configure(
            "CardHeading.TLabel",
            background=colors["card_bg"],
            foreground=colors["heading"],
            font=("Segoe UI Semibold", 10),
        )
        style.configure(
            "CardMuted.TLabel",
            background=colors["card_bg"],
            foreground=colors["muted_text"],
            font=("Segoe UI", 9),
        )
        style.configure(
            "FieldName.TLabel",
            background=colors["card_bg"],
            foreground=colors["muted_text"],
            font=("Segoe UI", 9),
        )
        style.configure(
            "Heading.TLabel",
            background=colors["app_bg"],
            foreground=colors["heading"],
            font=("Segoe UI Semibold", 12),
        )
        style.configure(
            "Muted.TLabel",
            background=colors["app_bg"],
            foreground=colors["muted_text"],
            font=("Segoe UI", 9),
        )
        style.configure(
            "Treeview",
            background=colors["panel_bg"],
            foreground=colors["text"],
            fieldbackground=colors["panel_bg"],
            bordercolor=colors["border"],
            rowheight=26,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Treeview.Heading",
            background=colors["field_bg"],
            foreground=colors["heading"],
            bordercolor=colors["border"],
            relief="flat",
            font=("Segoe UI Semibold", 10),
        )
        style.configure(
            "TLabelframe",
            background=colors["zone_bg"],
            foreground=colors["muted_text"],
            bordercolor=colors["zone_border"],
            relief="groove",
            borderwidth=1,
        )
        style.configure(
            "TLabelframe.Label",
            background=colors["app_bg"],
            foreground=colors["heading"],
            font=("Segoe UI Semibold", 10),
        )
        style.configure(
            "TEntry",
            padding=(8, 6),
            fieldbackground=colors["field_bg"],
            foreground=colors["text"],
            bordercolor=colors["border"],
            insertcolor=colors["text"],
        )
        style.configure("TCheckbutton", background=colors["app_bg"], foreground=colors["text"])
        style.configure(
            "TCombobox",
            padding=(8, 6),
            fieldbackground=colors["field_bg"],
            background=colors["field_bg"],
            foreground=colors["text"],
            arrowcolor=colors["muted_text"],
            bordercolor=colors["border"],
        )
        style.configure(
            "TButton",
            padding=(14, 8),
            background=colors["field_bg"],
            foreground=colors["text"],
            bordercolor=colors["border"],
            relief="flat",
            font=("Segoe UI Semibold", 10),
        )
        style.configure(
            "Primary.TButton",
            padding=(16, 9),
            background=colors["accent"],
            foreground=colors["heading"],
            bordercolor=colors["accent_active"],
            relief="flat",
            font=("Segoe UI Semibold", 10),
        )
        style.configure(
            "Danger.TButton",
            padding=(14, 8),
            background=colors["danger"],
            foreground=colors["heading"],
            bordercolor=colors["danger"],
            relief="flat",
            font=("Segoe UI Semibold", 10),
        )
        style.configure(
            "TNotebook",
            background=colors["app_bg"],
            borderwidth=0,
        )
        style.configure(
            "TNotebook.Tab",
            padding=(14, 8),
            background=colors["field_bg"],
            foreground=colors["muted_text"],
            borderwidth=0,
            font=("Segoe UI Semibold", 9),
        )
        style.map(
            "Treeview",
            background=[("selected", colors["accent"])],
            foreground=[("selected", colors["heading"])],
        )
        style.map("TButton", background=[("active", colors["field_bg_active"])])
        style.map(
            "TCombobox",
            fieldbackground=[
                ("readonly", colors["field_bg"]),
                ("disabled", colors["panel_bg"]),
            ],
            background=[
                ("readonly", colors["field_bg"]),
                ("active", colors["field_bg_active"]),
                ("disabled", colors["panel_bg"]),
            ],
            foreground=[
                ("readonly", colors["text"]),
                ("disabled", colors["muted_text"]),
            ],
            arrowcolor=[
                ("readonly", colors["muted_text"]),
                ("active", colors["text"]),
            ],
        )
        style.map("Primary.TButton", background=[("active", colors["accent_active"])])
        style.map(
            "TNotebook.Tab",
            background=[("selected", colors["card_bg"]), ("active", colors["field_bg_active"])],
            foreground=[("selected", colors["heading"]), ("active", colors["heading"])],
        )

    def configure_fonts(self):
        for font_name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont"):
            try:
                tkfont.nametofont(font_name).configure(family="Segoe UI", size=10)
            except tk.TclError:
                continue
        try:
            tkfont.nametofont("TkFixedFont").configure(family="Cascadia Mono", size=10)
        except tk.TclError:
            pass

    def apply_external_theme(self, style):
        try:
            import sv_ttk  # type: ignore
        except ImportError:
            style.theme_use("clam")
            return
        sv_ttk.set_theme("dark")

    def create_widgets(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_pane.grid(row=0, column=0, sticky="nsew")

        self.left_panel = ttk.Frame(self.main_pane, padding=14, width=528)
        self.left_panel.rowconfigure(3, weight=1)
        self.left_panel.columnconfigure(0, weight=1)
        self.main_pane.add(self.left_panel, weight=1)

        self.create_global_actions(self.left_panel)
        self.create_search(self.left_panel)
        self.create_mode_tabs(self.left_panel)
        self.create_right_panel(self.main_pane)
        self.root.after_idle(self.restore_main_pane_layout)
        self.root.after(250, self.restore_main_pane_layout)

    def restore_main_pane_layout(self):
        self.root.update_idletasks()
        window_width = max(self.root.winfo_width(), 980)
        left_width = min(528, max(420, window_width - 420))
        try:
            self.main_pane.sashpos(0, left_width)
        except tk.TclError:
            pass

    def create_global_actions(self, parent):
        actions = ttk.Frame(parent)
        actions.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        actions.columnconfigure(0, weight=1)
        ttk.Button(
            actions,
            text="Create/Update RM Manifest",
            command=self.create_or_update_rm_manifest,
            style="Primary.TButton",
        ).grid(row=0, column=0, sticky="ew")
        ttk.Button(
            actions,
            text="Build/Update GUI Manifest",
            command=self.build_update_gui_manifest,
            style="Primary.TButton",
        ).grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(
            actions,
            text="Build Groups",
            command=self.build_groups,
            style="Primary.TButton",
        ).grid(row=2, column=0, sticky="ew", pady=(8, 0))

    def create_search(self, parent):
        search_frame = ttk.Frame(parent)
        search_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        search_frame.columnconfigure(1, weight=1)

        ttk.Label(search_frame, text="Search").grid(row=0, column=0, sticky="w", padx=(0, 10))
        ttk.Entry(search_frame, textvariable=self.search_var, width=24).grid(row=0, column=1, sticky="ew")
        ttk.Button(search_frame, text="Clear", command=self.clear_search).grid(row=0, column=2, sticky="e", padx=(10, 0))
        ttk.Label(parent, textvariable=self.result_var, style="Muted.TLabel").grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 10))

    def create_mode_tabs(self, parent):
        self.mode_tabs = ttk.Notebook(parent)
        self.mode_tabs.grid(row=3, column=0, columnspan=2, sticky="nsew")
        self.mode_tabs.bind("<<NotebookTabChanged>>", self.on_mode_tab_changed)

        self.png_data_tab = ttk.Frame(self.mode_tabs, padding=14)
        self.png_data_tab.rowconfigure(1, weight=1)
        self.png_data_tab.columnconfigure(0, weight=1)
        self.check_rm_tab = ttk.Frame(self.mode_tabs, padding=14)
        self.check_rm_tab.columnconfigure(0, weight=1)
        self.create_group_tab = ttk.Frame(self.mode_tabs, padding=14)
        self.create_group_tab.rowconfigure(1, weight=1)
        self.create_group_tab.columnconfigure(0, weight=1)
        self.edit_group_tab = ttk.Frame(self.mode_tabs, padding=14)
        self.edit_group_tab.rowconfigure(1, weight=1)
        self.edit_group_tab.columnconfigure(0, weight=1)

        self.mode_tabs.add(self.png_data_tab, text="PNG DATA")
        self.mode_tabs.add(self.check_rm_tab, text="CHECK RM MANIFEST")
        self.mode_tabs.add(self.create_group_tab, text="CREATE GROUP")
        self.mode_tabs.add(self.edit_group_tab, text="EDIT GROUP")

        ttk.Label(
            self.png_data_tab,
            text="Raw PNG source",
            wraplength=360,
            style="Heading.TLabel",
        ).grid(row=0, column=0, sticky="nw")
        self.create_png_explorer(self.png_data_tab, row=1, column=0, columnspan=1, sticky="nsew")
        ttk.Label(
            self.check_rm_tab,
            text="RM Manifest inspection. Use the right panel to check metadata stored in the PNG files referenced by RM Manifest.",
            wraplength=360,
        ).grid(row=0, column=0, sticky="nw")
        self.create_check_rm_controls(self.check_rm_tab)
        ttk.Label(
            self.create_group_tab,
            text="CREATE GROUP",
            wraplength=360,
        ).grid(row=0, column=0, sticky="nw")
        self.create_group_builder(self.create_group_tab, builder_key="create")
        edit_header = ttk.Frame(self.edit_group_tab)
        edit_header.grid(row=0, column=0, sticky="ew")
        edit_header.columnconfigure(0, weight=1)
        edit_header.columnconfigure(1, weight=1)
        edit_header.columnconfigure(2, weight=1)
        ttk.Label(
            edit_header,
            text="EDIT GROUP",
            wraplength=180,
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.edit_group_save_button = ttk.Button(
            edit_header,
            text="Save Group",
            command=self.save_create_group_builder,
            style="Primary.TButton",
        )
        self.edit_group_save_button.grid(row=0, column=1, sticky="ew", padx=(0, 4))
        self.edit_group_cancel_button = ttk.Button(
            edit_header,
            text="Cancel",
            command=self.cancel_edit_group,
        )
        self.edit_group_cancel_button.grid(row=0, column=2, sticky="ew", padx=(4, 0))
        self.edit_group_save_button.state(["disabled"])
        self.edit_group_cancel_button.state(["disabled"])
        self.edit_group_empty_label = ttk.Label(
            self.edit_group_tab,
            text="Select a group in GUI Manifest and press Edit.",
            wraplength=420,
            style="Muted.TLabel",
        )
        self.edit_group_empty_label.grid(row=1, column=0, sticky="nw", pady=(12, 0))
        self.edit_group_form_holder = ttk.Frame(self.edit_group_tab)
        self.edit_group_form_holder.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        self.edit_group_form_holder.columnconfigure(0, weight=1)
        self.edit_group_form_holder.grid_remove()

    def create_group_builder(self, parent, builder_key="create", show_cancel=False):
        form = ttk.LabelFrame(parent, text="Group Builder", padding=8)
        form.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        ttk.Label(form, text="group").grid(row=0, column=0, sticky="e", padx=(0, 10), pady=(0, 4))
        ttk.Entry(form, textvariable=self.group_id_var).grid(row=0, column=1, columnspan=3, sticky="ew", pady=(0, 4))
        ttk.Label(form, text="role").grid(row=1, column=0, sticky="e", padx=(0, 10), pady=(0, 4))
        ttk.Entry(form, textvariable=self.group_role_var).grid(row=1, column=1, columnspan=3, sticky="ew", pady=(0, 4))
        ttk.Label(form, text="tags").grid(row=2, column=0, sticky="e", padx=(0, 10), pady=(0, 4))
        ttk.Entry(form, textvariable=self.group_tags_var).grid(row=2, column=1, columnspan=3, sticky="ew", pady=(0, 4))

        ttk.Label(form, text="rect").grid(row=3, column=0, sticky="e", padx=(0, 10), pady=(0, 4))
        self.create_quad_inputs(
            form,
            3,
            (self.group_rect_x_var, self.group_rect_y_var, self.group_rect_w_var, self.group_rect_h_var),
        )

        ttk.Label(form, text="hit_rect").grid(row=4, column=0, sticky="e", padx=(0, 10), pady=(0, 4))
        self.create_quad_inputs(
            form,
            4,
            (self.group_hit_x_var, self.group_hit_y_var, self.group_hit_w_var, self.group_hit_h_var),
        )

        ttk.Label(form, text="scale").grid(row=5, column=0, sticky="e", padx=(0, 10), pady=(0, 4))
        ttk.Entry(form, textvariable=self.group_scale_var, width=8).grid(row=5, column=1, sticky="w", pady=(0, 4))
        ttk.Checkbutton(form, text="hide_rect", variable=self.group_hide_rect_var).grid(
            row=5, column=2, columnspan=2, sticky="w", padx=(12, 0), pady=(0, 4)
        )

        ttk.Label(form, text="layer type").grid(row=6, column=0, sticky="e", padx=(0, 10), pady=(6, 4))
        type_buttons = ttk.Frame(form)
        type_buttons.grid(row=6, column=1, columnspan=3, sticky="ew", pady=(6, 4))
        type_buttons.columnconfigure(0, weight=1)
        type_buttons.columnconfigure(1, weight=1)
        ttk.Button(
            type_buttons,
            text="Graphic",
            command=lambda: self.select_builder_layer_type("Graphic"),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(
            type_buttons,
            text="Text",
            command=lambda: self.select_builder_layer_type("Text"),
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0))
        ttk.Label(form, textvariable=self.layer_type_var).grid(
            row=7, column=1, columnspan=3, sticky="w", pady=(0, 4)
        )

        graphic_builder_frame = ttk.LabelFrame(form, text="Graphic Layer Form", padding=8)
        graphic_builder_frame.grid(row=8, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        graphic_builder_frame.columnconfigure(1, weight=1)
        ttk.Label(graphic_builder_frame, text="layer:").grid(row=0, column=0, sticky="w", pady=(0, 4))
        graphic_layer_box = ttk.Combobox(
            graphic_builder_frame,
            textvariable=self.graphic_layer_choice_var,
            state="readonly",
            values=(),
        )
        graphic_layer_box.grid(row=0, column=1, sticky="ew", pady=(0, 4))
        graphic_layer_box.bind("<<ComboboxSelected>>", self.on_graphic_layer_choice)
        ttk.Button(graphic_builder_frame, text="New layer", command=self.select_new_graphic_layer).grid(
            row=0, column=2, sticky="ew", padx=(8, 0), pady=(0, 4)
        )

        ttk.Label(graphic_builder_frame, text="resource_key:").grid(row=1, column=0, sticky="w", pady=(0, 4))
        ttk.Entry(graphic_builder_frame, textvariable=self.graphic_resource_key_var).grid(
            row=1, column=1, sticky="ew", pady=(0, 4)
        )
        ttk.Button(graphic_builder_frame, text="Choose", command=self.show_rm_manifest_workbench).grid(
            row=1, column=2, sticky="ew", padx=(8, 0), pady=(0, 4)
        )
        self.create_xy_percent_inputs(graphic_builder_frame, row=2)

        text_builder_frame = ttk.LabelFrame(form, text="Text Layer Form", padding=8)
        text_builder_frame.grid(row=9, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        text_builder_frame.columnconfigure(1, weight=1)
        ttk.Label(text_builder_frame, text="layer:").grid(row=0, column=0, sticky="w", pady=(0, 4))
        text_layer_box = ttk.Combobox(
            text_builder_frame,
            textvariable=self.text_layer_choice_var,
            state="readonly",
            values=(),
        )
        text_layer_box.grid(row=0, column=1, sticky="ew", pady=(0, 4))
        text_layer_box.bind("<<ComboboxSelected>>", self.on_text_layer_choice)
        ttk.Button(text_builder_frame, text="New layer", command=self.select_new_text_layer).grid(
            row=0, column=2, columnspan=2, sticky="ew", padx=(8, 0), pady=(0, 4)
        )

        ttk.Label(text_builder_frame, text="text").grid(row=1, column=0, sticky="w", pady=(0, 4))
        ttk.Entry(text_builder_frame, textvariable=self.text_value_var).grid(
            row=1, column=1, columnspan=3, sticky="ew", pady=(0, 4)
        )
        ttk.Label(text_builder_frame, text="font").grid(row=2, column=0, sticky="w", pady=(0, 4))
        font_box = ttk.Combobox(
            text_builder_frame,
            textvariable=self.font_path_var,
            values=self.available_fonts,
        )
        font_box.grid(row=2, column=1, columnspan=3, sticky="ew", pady=(0, 4))
        font_box.bind("<<ComboboxSelected>>", self.on_builder_font_selected)
        ttk.Label(text_builder_frame, text="height").grid(row=3, column=0, sticky="w", pady=(0, 4))
        ttk.Entry(text_builder_frame, textvariable=self.text_height_var).grid(
            row=3, column=1, sticky="ew", pady=(0, 4)
        )
        ttk.Label(text_builder_frame, text="color").grid(row=3, column=2, sticky="w", padx=(8, 0), pady=(0, 4))
        ttk.Entry(text_builder_frame, textvariable=self.font_color_hex_var).grid(
            row=3, column=3, sticky="ew", pady=(0, 4)
        )
        self.create_xy_percent_inputs(text_builder_frame, row=4)

        if not show_cancel:
            footer = ttk.Frame(form)
            footer.grid(row=10, column=0, columnspan=4, sticky="ew", pady=(8, 0))
            footer.columnconfigure(0, weight=1)
            ttk.Button(
                footer,
                text="Save Group",
                command=self.save_create_group_builder,
                style="Primary.TButton",
            ).grid(
                row=0,
                column=0,
                sticky="ew",
            )
        self.group_builder_sections[builder_key] = {
            "form": form,
            "graphic": graphic_builder_frame,
            "text": text_builder_frame,
            "graphic_layer_box": graphic_layer_box,
            "text_layer_box": text_layer_box,
        }
        self.graphic_builder_frame = graphic_builder_frame
        self.text_builder_frame = text_builder_frame
        self.on_layer_type_change()

    def create_xy_percent_inputs(self, parent, row):
        ttk.Label(parent, text="x").grid(row=row, column=0, sticky="w", pady=(0, 2))
        ttk.Entry(parent, textvariable=self.layer_x_var, width=8).grid(row=row, column=1, sticky="ew", pady=(0, 2))
        ttk.Label(parent, text="y").grid(row=row, column=2, sticky="w", padx=(8, 0), pady=(0, 2))
        ttk.Entry(parent, textvariable=self.layer_y_var, width=8).grid(row=row, column=3, sticky="ew", pady=(0, 2))
        ttk.Label(parent, text="scale w%").grid(row=row + 1, column=0, sticky="w", pady=(0, 2))
        ttk.Entry(parent, textvariable=self.layer_scale_w_var, width=8).grid(row=row + 1, column=1, sticky="ew", pady=(0, 2))
        ttk.Label(parent, text="scale h%").grid(row=row + 1, column=2, sticky="w", padx=(8, 0), pady=(0, 2))
        ttk.Entry(parent, textvariable=self.layer_scale_h_var, width=8).grid(row=row + 1, column=3, sticky="ew", pady=(0, 2))

    def create_check_rm_controls(self, parent):
        controls = ttk.LabelFrame(parent, text="RM Manifest Actions", padding=14)
        controls.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        controls.columnconfigure(0, weight=1)
        ttk.Button(controls, text="EDIT PNG Metadata", command=self.edit_manifest_png_metadata).grid(
            row=0, column=0, sticky="ew"
        )
        self.rm_metadata_editor_holder = ttk.Frame(controls)
        self.rm_metadata_editor_holder.grid(row=1, column=0, sticky="ew")
        self.create_metadata_editor(
            self.rm_metadata_editor_holder,
            row=0,
            title="PNG Metadata Editor",
            button_text="APPLY",
        )
        self.rm_metadata_editor_holder.grid_remove()

    def create_png_explorer(self, parent, row=0, column=0, columnspan=2, sticky="nsew"):
        explorer = ttk.LabelFrame(parent, text="PNG Explorer", padding=14)
        explorer.grid(row=row, column=column, columnspan=columnspan, sticky=sticky)
        explorer.rowconfigure(0, weight=1)
        explorer.columnconfigure(0, weight=1)
        self.create_png_tree(explorer)

    def create_png_tree(self, parent):
        self.png_tree = ttk.Treeview(parent, columns=("size",), show="tree headings", height=16)
        self.png_tree.heading("#0", text="PNG")
        self.png_tree.heading("size", text="Size")
        self.png_tree.column("#0", width=260)
        self.png_tree.column("size", width=86, anchor="center", stretch=False)
        self.png_tree.grid(row=0, column=0, sticky="nsew")
        self.png_tree.bind("<<TreeviewSelect>>", self.on_png_select)

        tree_scroll = ttk.Scrollbar(parent, orient="vertical", command=self.png_tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.png_tree.configure(yscrollcommand=tree_scroll.set)

        ttk.Button(parent, text="Copy resource key", command=self.get_png_resource).grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0)
        )

    def create_group_config_tree(self, parent):
        self.group_config_tree = ttk.Treeview(parent, columns=("type", "value"), show="tree headings", height=16)
        self.group_config_tree.heading("#0", text="Group / layer")
        self.group_config_tree.heading("type", text="Type")
        self.group_config_tree.heading("value", text="Resource / text")
        self.group_config_tree.column("#0", width=230)
        self.group_config_tree.column("type", width=90, anchor="center")
        self.group_config_tree.column("value", width=360)
        self.group_config_tree.grid(row=0, column=0, sticky="nsew")
        self.group_config_tree.bind("<<TreeviewSelect>>", self.on_group_config_select)

        tree_scroll = ttk.Scrollbar(parent, orient="vertical", command=self.group_config_tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.group_config_tree.configure(yscrollcommand=tree_scroll.set)

    def create_manifest_tree(self, parent):
        self.manifest_tree = ttk.Treeview(parent, columns=("path", "frame", "meta"), show="tree headings", height=16)
        self.manifest_tree.heading("#0", text="Resource key")
        self.manifest_tree.heading("path", text="PNG path")
        self.manifest_tree.heading("frame", text="Frame")
        self.manifest_tree.heading("meta", text="Metadata")
        self.manifest_tree.column("#0", width=240)
        self.manifest_tree.column("path", width=300)
        self.manifest_tree.column("frame", width=80, anchor="center")
        self.manifest_tree.column("meta", width=100, anchor="center")
        self.manifest_tree.grid(row=0, column=0, sticky="nsew")
        self.manifest_tree.bind("<<TreeviewSelect>>", self.on_manifest_select)

        tree_scroll = ttk.Scrollbar(parent, orient="vertical", command=self.manifest_tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.manifest_tree.configure(yscrollcommand=tree_scroll.set)

    def create_png_manifest_tree(self, parent):
        self.png_manifest_tree = ttk.Treeview(parent, columns=("path", "frame", "meta"), show="tree headings", height=16)
        self.png_manifest_tree.heading("#0", text="Resource key")
        self.png_manifest_tree.heading("path", text="PNG path")
        self.png_manifest_tree.heading("frame", text="Frame")
        self.png_manifest_tree.heading("meta", text="Metadata")
        self.png_manifest_tree.column("#0", width=240)
        self.png_manifest_tree.column("path", width=300)
        self.png_manifest_tree.column("frame", width=80, anchor="center")
        self.png_manifest_tree.column("meta", width=100, anchor="center")
        self.png_manifest_tree.grid(row=0, column=0, sticky="nsew")
        self.png_manifest_tree.bind("<<TreeviewSelect>>", self.on_png_manifest_select)

        tree_scroll = ttk.Scrollbar(parent, orient="vertical", command=self.png_manifest_tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.png_manifest_tree.configure(yscrollcommand=tree_scroll.set)

    def create_metadata_editor(
        self,
        parent,
        row=2,
        column=0,
        columnspan=1,
        title="PNG Metadata Editor",
        button_text="Save PNG metadata",
    ):
        form = ttk.Frame(parent, padding=14, style="Card.TFrame")
        form.grid(row=row, column=column, columnspan=columnspan, sticky="ew", pady=(12, 0))
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        ttk.Label(form, text=title, style="CardHeading.TLabel").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))

        ttk.Label(form, text="PNG", style="FieldName.TLabel").grid(row=1, column=0, sticky="e", padx=(0, 10), pady=(0, 6))
        ttk.Label(form, textvariable=self.resource_key_var, style="CardMuted.TLabel").grid(
            row=1, column=1, columnspan=3, sticky="w", pady=(0, 6)
        )

        ttk.Label(form, text="Path", style="FieldName.TLabel").grid(row=2, column=0, sticky="e", padx=(0, 10), pady=(0, 6))
        ttk.Label(form, textvariable=self.path_var, style="CardMuted.TLabel").grid(
            row=2, column=1, columnspan=3, sticky="w", pady=(0, 6)
        )

        ttk.Label(form, text="Size", style="FieldName.TLabel").grid(row=3, column=0, sticky="e", padx=(0, 10), pady=(0, 8))
        ttk.Label(form, textvariable=self.png_size_var, style="CardMuted.TLabel").grid(row=3, column=1, sticky="w", pady=(0, 8))

        ttk.Label(form, text="Frame width", style="FieldName.TLabel").grid(row=4, column=0, sticky="e", padx=(0, 10), pady=(4, 8))
        ttk.Entry(form, textvariable=self.frame_width_var, width=8).grid(row=4, column=1, sticky="w", pady=(4, 8))

        ttk.Label(form, text="Frame height", style="FieldName.TLabel").grid(row=4, column=2, sticky="e", padx=(18, 10), pady=(4, 8))
        ttk.Entry(form, textvariable=self.frame_height_var, width=8).grid(row=4, column=3, sticky="w", pady=(4, 8))

        ttk.Label(form, textvariable=self.details_var, wraplength=620, style="CardMuted.TLabel").grid(
            row=5, column=0, columnspan=4, sticky="w", pady=(2, 10)
        )
        ttk.Button(form, text=button_text, command=self.save_png_metadata).grid(
            row=6, column=0, columnspan=4, sticky="ew"
        )

    def create_group_config_editor(self, parent, row=0):
        form = ttk.LabelFrame(parent, text="Group Editor", padding=8)
        form.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        ttk.Label(form, textvariable=self.group_mode_var).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        ttk.Label(form, text="layer type").grid(row=0, column=2, sticky="w", padx=(8, 0), pady=(0, 6))
        layer_type = ttk.Combobox(
            form,
            textvariable=self.layer_type_var,
            values=("Graphic", "Text"),
            state="readonly",
            width=10,
        )
        layer_type.grid(row=0, column=3, sticky="ew", pady=(0, 6))
        layer_type.bind("<<ComboboxSelected>>", self.on_layer_type_change)

        ttk.Label(form, text="group").grid(row=1, column=0, sticky="w", pady=(0, 4))
        ttk.Entry(form, textvariable=self.group_id_var, width=18).grid(row=1, column=1, sticky="ew", pady=(0, 4))
        ttk.Label(form, text="role").grid(row=1, column=2, sticky="w", padx=(8, 0), pady=(0, 4))
        ttk.Entry(form, textvariable=self.group_role_var).grid(row=1, column=3, sticky="ew", pady=(0, 4))

        ttk.Label(form, text="tags").grid(row=2, column=0, sticky="w", pady=(0, 4))
        ttk.Entry(form, textvariable=self.group_tags_var).grid(row=2, column=1, columnspan=3, sticky="ew", pady=(0, 4))

        ttk.Label(form, text="rect").grid(row=3, column=0, sticky="w", pady=(0, 4))
        self.create_quad_inputs(
            form,
            3,
            (self.group_rect_x_var, self.group_rect_y_var, self.group_rect_w_var, self.group_rect_h_var),
        )

        ttk.Label(form, text="hit_rect").grid(row=4, column=0, sticky="w", pady=(0, 4))
        self.create_quad_inputs(
            form,
            4,
            (self.group_hit_x_var, self.group_hit_y_var, self.group_hit_w_var, self.group_hit_h_var),
        )

        ttk.Label(form, text="scale").grid(row=5, column=0, sticky="w", pady=(0, 4))
        ttk.Entry(form, textvariable=self.group_scale_var, width=8).grid(row=5, column=1, sticky="ew", pady=(0, 4))
        ttk.Checkbutton(form, text="hide debug rect", variable=self.group_hide_rect_var).grid(
            row=5, column=2, columnspan=2, sticky="w", padx=(8, 0), pady=(0, 4)
        )

        ttk.Label(form, text="layers in group").grid(row=6, column=0, sticky="w", pady=(8, 4))
        self.create_group_editor_layers_tree(form, row=6)

        ttk.Label(form, text="layer").grid(row=7, column=0, sticky="w", pady=(8, 4))
        ttk.Entry(form, textvariable=self.layer_name_var, width=18).grid(row=7, column=1, sticky="ew", pady=(8, 4))
        ttk.Label(form, text="target").grid(row=7, column=2, sticky="w", padx=(8, 0), pady=(8, 4))
        ttk.Entry(form, textvariable=self.target_id_var).grid(row=7, column=3, sticky="ew", pady=(8, 4))

        ttk.Label(form, text="layer x").grid(row=8, column=0, sticky="w", pady=(0, 4))
        ttk.Entry(form, textvariable=self.layer_x_var, width=8).grid(row=8, column=1, sticky="ew", pady=(0, 4))
        ttk.Label(form, text="layer y").grid(row=8, column=2, sticky="w", padx=(8, 0), pady=(0, 4))
        ttk.Entry(form, textvariable=self.layer_y_var, width=8).grid(row=8, column=3, sticky="ew", pady=(0, 4))

        ttk.Label(form, text="resource").grid(row=9, column=0, sticky="w", pady=(0, 4))
        ttk.Entry(form, textvariable=self.graphic_resource_key_var).grid(
            row=9, column=1, columnspan=2, sticky="ew", pady=(0, 4)
        )
        resource_buttons = ttk.Frame(form)
        resource_buttons.grid(row=9, column=3, sticky="ew", padx=(8, 0), pady=(0, 4))
        resource_buttons.columnconfigure(0, weight=1)
        resource_buttons.columnconfigure(1, weight=1)
        ttk.Button(resource_buttons, text="Choose", command=self.show_rm_manifest_workbench).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        ttk.Button(resource_buttons, text="Clear", command=self.clear_graphic_resource).grid(
            row=0, column=1, sticky="ew", padx=(4, 0)
        )

        ttk.Button(
            form,
            text="Save group metadata",
            command=self.save_group_config_metadata_only,
            style="Primary.TButton",
        ).grid(row=10, column=0, columnspan=4, sticky="ew", pady=(4, 0))
        ttk.Button(
            form,
            text="Save graphic layer",
            command=self.upsert_group_config_layer,
            style="Primary.TButton",
        ).grid(row=11, column=0, columnspan=4, sticky="ew", pady=(4, 0))
        ttk.Button(
            form,
            text="Save layer position",
            command=self.save_group_config_layer_position,
        ).grid(row=12, column=0, columnspan=4, sticky="ew", pady=(4, 0))
        ttk.Button(
            form,
            text="Delete current layer",
            command=self.delete_group_config_layer,
            style="Danger.TButton",
        ).grid(row=13, column=0, columnspan=4, sticky="ew", pady=(4, 0))
        footer = ttk.Frame(form)
        footer.grid(row=14, column=0, columnspan=4, sticky="ew", pady=(4, 0))
        footer.columnconfigure(0, weight=1)
        footer.columnconfigure(1, weight=1)
        ttk.Button(footer, text="Open Group Explorer", command=self.show_group_config_workbench).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        ttk.Button(footer, text="Clear form", command=self.clear_group_config_form).grid(
            row=0, column=1, sticky="ew", padx=(4, 0)
        )

    def create_quad_inputs(self, parent, row, variables):
        labels = ("x", "y", "w", "h")
        holder = ttk.Frame(parent)
        holder.grid(row=row, column=1, columnspan=3, sticky="ew", pady=(0, 2))
        for index, variable in enumerate(variables):
            holder.columnconfigure(index * 2 + 1, weight=1)
            ttk.Label(holder, text=labels[index]).grid(row=0, column=index * 2, sticky="w", padx=(0 if index == 0 else 8, 3))
            ttk.Entry(holder, textvariable=variable, width=6).grid(row=0, column=index * 2 + 1, sticky="ew")

    def create_group_editor_layers_tree(self, parent, row):
        holder = ttk.Frame(parent)
        holder.grid(row=row, column=1, columnspan=3, sticky="ew", pady=(8, 4))
        holder.columnconfigure(0, weight=1)
        self.group_editor_layers_tree = ttk.Treeview(
            holder,
            columns=("type", "value", "position"),
            show="tree headings",
            height=4,
        )
        self.group_editor_layers_tree.heading("#0", text="Layer")
        self.group_editor_layers_tree.heading("type", text="Type")
        self.group_editor_layers_tree.heading("value", text="Resource / text")
        self.group_editor_layers_tree.heading("position", text="Pos")
        self.group_editor_layers_tree.column("#0", width=130)
        self.group_editor_layers_tree.column("type", width=70, anchor="center")
        self.group_editor_layers_tree.column("value", width=250)
        self.group_editor_layers_tree.column("position", width=70, anchor="center")
        self.group_editor_layers_tree.grid(row=0, column=0, sticky="ew")
        self.group_editor_layers_tree.bind("<<TreeviewSelect>>", self.on_group_editor_layer_select)

    def create_text_layer_editor(self, parent, row=1):
        form = ttk.LabelFrame(parent, text="Text Layer Editor", padding=8)
        self.text_layer_editor_frame = form
        form.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        ttk.Label(form, text="text").grid(row=0, column=0, sticky="w", pady=(0, 4))
        ttk.Entry(form, textvariable=self.text_value_var).grid(row=0, column=1, columnspan=3, sticky="ew", pady=(0, 4))

        ttk.Label(form, text="text_key").grid(row=1, column=0, sticky="w", pady=(0, 4))
        ttk.Entry(form, textvariable=self.text_key_var).grid(row=1, column=1, columnspan=3, sticky="ew", pady=(0, 4))

        ttk.Label(form, text="w").grid(row=2, column=0, sticky="w", pady=(0, 4))
        ttk.Entry(form, textvariable=self.text_width_var, width=8).grid(row=2, column=1, sticky="ew", pady=(0, 4))

        ttk.Label(form, text="h").grid(row=2, column=2, sticky="w", padx=(8, 0), pady=(0, 4))
        ttk.Entry(form, textvariable=self.text_height_var, width=8).grid(row=2, column=3, sticky="ew", pady=(0, 4))

        ttk.Label(form, text="fit").grid(row=3, column=0, sticky="w", pady=(0, 4))
        ttk.Combobox(
            form,
            textvariable=self.text_fit_mode_var,
            values=("none", "width", "height", "contain", "stretch"),
            state="readonly",
        ).grid(row=3, column=1, sticky="ew", pady=(0, 4))

        ttk.Label(form, text="font_size").grid(row=3, column=2, sticky="w", padx=(8, 0), pady=(0, 4))
        ttk.Entry(form, textvariable=self.font_size_var, width=8).grid(row=3, column=3, sticky="ew", pady=(0, 4))

        ttk.Label(form, text="font_name").grid(row=4, column=0, sticky="w", pady=(0, 4))
        ttk.Entry(form, textvariable=self.font_name_var).grid(row=4, column=1, columnspan=3, sticky="ew", pady=(0, 4))

        ttk.Label(form, text="font_path").grid(row=5, column=0, sticky="w", pady=(0, 4))
        ttk.Entry(form, textvariable=self.font_path_var).grid(row=5, column=1, columnspan=2, sticky="ew", pady=(0, 4))
        ttk.Button(form, text="Browse", command=self.browse_text_font_path).grid(
            row=5, column=3, sticky="ew", padx=(8, 0), pady=(0, 4)
        )

        ttk.Label(form, text="color").grid(row=6, column=0, sticky="w", pady=(0, 4))
        ttk.Entry(form, textvariable=self.font_color_r_var, width=4).grid(row=6, column=1, sticky="ew", pady=(0, 4))
        ttk.Entry(form, textvariable=self.font_color_g_var, width=4).grid(row=6, column=2, sticky="ew", padx=(8, 0), pady=(0, 4))
        ttk.Entry(form, textvariable=self.font_color_b_var, width=4).grid(row=6, column=3, sticky="ew", padx=(8, 0), pady=(0, 4))

        ttk.Checkbutton(form, text="antialias", variable=self.font_antialias_var).grid(
            row=7, column=0, columnspan=2, sticky="w", pady=(0, 4)
        )
        ttk.Button(form, text="Pick color", command=self.pick_text_color).grid(
            row=7, column=2, columnspan=2, sticky="ew", padx=(8, 0), pady=(0, 4)
        )
        ttk.Button(form, text="Save text layer", command=self.save_group_config_text_layer).grid(
            row=8, column=0, columnspan=4, sticky="ew", pady=(4, 0)
        )

    def show_text_layer_editor(self):
        if hasattr(self, "text_layer_editor_frame"):
            self.text_layer_editor_frame.grid()

    def hide_text_layer_editor(self):
        if hasattr(self, "text_layer_editor_frame"):
            self.text_layer_editor_frame.grid_remove()

    def on_layer_type_change(self, _event=None):
        if self.layer_type_var.get() == "Text":
            for sections in self.group_builder_sections.values():
                sections["graphic"].grid_remove()
                sections["text"].grid()
            if not self.text_layer_choice_var.get().strip() and not self.layer_name_var.get().strip():
                self.select_new_text_layer()
            self.show_text_layer_editor()
            self.status_var.set("Text layer mode")
            self.update_group_config_preview()
            return
        for sections in self.group_builder_sections.values():
            sections["graphic"].grid()
            sections["text"].grid_remove()
        self.hide_text_layer_editor()
        self.status_var.set("Graphic layer mode")
        self.update_group_config_preview()

    def select_builder_layer_type(self, layer_type):
        self.layer_type_var.set(layer_type)
        self.on_layer_type_change()

    def trace_create_group_preview_vars(self):
        variables = (
            self.group_id_var,
            self.group_role_var,
            self.group_tags_var,
            self.group_rect_x_var,
            self.group_rect_y_var,
            self.group_rect_w_var,
            self.group_rect_h_var,
            self.group_hit_x_var,
            self.group_hit_y_var,
            self.group_hit_w_var,
            self.group_hit_h_var,
            self.group_scale_var,
            self.group_hide_rect_var,
            self.layer_type_var,
            self.layer_name_var,
            self.graphic_layer_choice_var,
            self.layer_x_var,
            self.layer_y_var,
            self.layer_scale_w_var,
            self.layer_scale_h_var,
            self.graphic_resource_key_var,
            self.text_value_var,
            self.text_height_var,
            self.font_path_var,
            self.font_color_hex_var,
        )
        for variable in variables:
            variable.trace_add("write", lambda *_args: self.update_group_config_preview())

    def update_group_config_preview(self):
        if not hasattr(self, "group_config_preview_text"):
            return
        payload = self.build_group_config_draft()
        if self.edit_group_active and self.edit_group_id:
            payload = payload.get("groups", {}).get(self.edit_group_id, {})
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        self.group_config_preview_text.configure(state="normal")
        self.group_config_preview_text.delete("1.0", tk.END)
        self.group_config_preview_text.insert("1.0", text)
        self.group_config_preview_text.configure(state="disabled")

    def build_group_config_draft(self):
        group_id = self.group_id_var.get().strip() or "<group_id>"
        group_payload = None
        try:
            group_config.reload_group_config()
            group_payload = copy.deepcopy(group_config.get_group_config(group_id))
        except Exception:
            group_payload = {
                "role": "",
                "tags": [],
                "rect": [0, 0, 0, 0],
                "hit_rect": [0, 0, 0, 0],
                "scale_factor": 1.0,
                "hide_rect": True,
                "manifest_targets": {},
                "layers": [],
            }
        group_payload["role"] = self.group_role_var.get().strip()
        group_payload["tags"] = self.parse_tags(self.group_tags_var.get())
        group_payload["rect"] = [
            self.safe_int(self.group_rect_x_var.get()),
            self.safe_int(self.group_rect_y_var.get()),
            self.safe_int(self.group_rect_w_var.get()),
            self.safe_int(self.group_rect_h_var.get()),
        ]
        group_payload["hit_rect"] = [
            self.safe_int(self.group_hit_x_var.get()),
            self.safe_int(self.group_hit_y_var.get()),
            self.safe_int(self.group_hit_w_var.get()),
            self.safe_int(self.group_hit_h_var.get()),
        ]
        try:
            group_payload["scale_factor"] = float(self.group_scale_var.get().strip() or "1.0")
        except ValueError:
            group_payload["scale_factor"] = 1.0
        group_payload["hide_rect"] = bool(self.group_hide_rect_var.get())

        layer = self.build_current_layer_draft()
        if layer:
            layers = group_payload.setdefault("layers", [])
            layer_name = layer["name"]
            for index, existing_layer in enumerate(layers):
                if existing_layer.get("name") == layer_name:
                    layers[index] = layer
                    break
            else:
                layers.append(layer)
        return {"groups": {group_id: group_payload}}

    def build_current_layer_draft(self):
        position = [self.safe_int(self.layer_x_var.get()), self.safe_int(self.layer_y_var.get())]
        scale_percent = [
            max(1, self.safe_int(self.layer_scale_w_var.get(), 100)),
            max(1, self.safe_int(self.layer_scale_h_var.get(), 100)),
        ]
        if self.layer_type_var.get() == "Text":
            layer_name = self.get_builder_layer_name("text")
            if not layer_name:
                return None
            style = {
                "font_path": self.font_path_var.get().strip() or None,
                "font_size": self.safe_int(self.font_size_var.get(), 24),
                "color": list(self.parse_hex_color(self.font_color_hex_var.get())),
                "antialias": bool(self.font_antialias_var.get()),
            }
            return {
                "name": layer_name,
                "type": "text",
                "text": self.text_value_var.get(),
                "height": max(1, self.safe_int(self.text_height_var.get(), 1)),
                "scale_percent": scale_percent,
                "position": position,
                "style": style,
            }
        layer_name = self.get_builder_layer_name("image")
        if not layer_name:
            return None
        return {
            "name": layer_name,
            "type": "image",
            "resource_key": self.get_graphic_resource_key(),
            "scale_percent": scale_percent,
            "position": position,
        }

    def get_builder_layer_name(self, layer_type):
        current_name = self.layer_name_var.get().strip()
        if current_name:
            return current_name
        if layer_type == "text":
            return self.create_layer_name_from_text_fields()
        resource_key = self.get_graphic_resource_key()
        return self.create_layer_name_from_resource_key(resource_key)

    def set_graphic_resource_key(self, resource_key):
        self.graphic_resource_full_key = str(resource_key or "").strip()
        self.graphic_resource_key_var.set(self.create_layer_name_from_resource_key(self.graphic_resource_full_key))

    def get_graphic_resource_key(self):
        if self.graphic_resource_full_key:
            return self.graphic_resource_full_key
        return self.graphic_resource_key_var.get().strip()

    def clear_graphic_resource_key(self):
        self.graphic_resource_full_key = ""
        self.graphic_resource_key_var.set("")

    def create_layer_name_from_text_fields(self):
        selected_layer = self.text_layer_choice_var.get().strip()
        if selected_layer:
            return selected_layer
        group_id = self.group_id_var.get().strip()
        if group_id:
            try:
                group_payload = group_config.get_group_config(group_id)
            except Exception:
                group_payload = {}
            return self.create_next_text_layer_name(group_payload)
        if self.text_value_var.get().strip():
            return "text_1"
        return ""

    @staticmethod
    def create_layer_name_from_resource_key(resource_key):
        name = str(resource_key or "").strip().replace("\\", "/")
        if not name:
            return ""
        name = name.rsplit("/", 1)[-1].rsplit(".", 1)[-1]
        name = re.sub(r"[^0-9A-Za-z_]+", "_", name).strip("_").lower()
        return name

    @staticmethod
    def create_next_text_layer_name(group_payload):
        used = {
            layer.get("name", "")
            for layer in group_payload.get("layers", ())
            if layer.get("name")
        }
        index = 1
        while f"text_{index}" in used:
            index += 1
        return f"text_{index}"

    def refresh_graphic_layer_choices(self, group_payload=None, selected_layer_name=""):
        group_payload = group_payload or {}
        image_layer_names = [
            layer.get("name", "")
            for layer in group_payload.get("layers", ())
            if layer.get("type", "image") == "image" and layer.get("name")
        ]
        values = tuple(image_layer_names)
        for sections in self.group_builder_sections.values():
            layer_box = sections.get("graphic_layer_box")
            if layer_box is not None:
                layer_box.configure(values=values)
        if selected_layer_name in image_layer_names:
            self.graphic_layer_choice_var.set(selected_layer_name)
        else:
            self.graphic_layer_choice_var.set("")

    def refresh_text_layer_choices(self, group_payload=None, selected_layer_name=""):
        group_payload = group_payload or {}
        text_layer_names = [
            layer.get("name", "")
            for layer in group_payload.get("layers", ())
            if layer.get("type", "image") == "text" and layer.get("name")
        ]
        values = tuple(text_layer_names)
        for sections in self.group_builder_sections.values():
            layer_box = sections.get("text_layer_box")
            if layer_box is not None:
                layer_box.configure(values=values)
        if selected_layer_name in text_layer_names:
            self.text_layer_choice_var.set(selected_layer_name)
        else:
            self.text_layer_choice_var.set("")

    def on_graphic_layer_choice(self, _event=None):
        layer_name = self.graphic_layer_choice_var.get().strip()
        if not layer_name:
            self.select_new_graphic_layer()
            return
        group_id = self.group_id_var.get().strip()
        if not group_id:
            return
        try:
            group_payload = group_config.get_group_config(group_id)
            layer_payload = group_config.get_layer_config(group_id, layer_name)
        except Exception as error:
            self.status_var.set(str(error))
            return
        if layer_payload.get("type", "image") != "image":
            return
        self.fill_group_config_form_from_layer_payload(group_id, group_payload, layer_payload)
        self.status_var.set(f"Editing layer resource_key: {group_id}.{layer_name}")

    def select_new_graphic_layer(self):
        self.graphic_layer_choice_var.set("")
        self.layer_name_var.set("")
        self.clear_graphic_resource_key()
        self.layer_x_var.set("0")
        self.layer_y_var.set("0")
        self.status_var.set("New graphic layer")

    def on_text_layer_choice(self, _event=None):
        layer_name = self.text_layer_choice_var.get().strip()
        if not layer_name:
            self.select_new_text_layer()
            return
        group_id = self.group_id_var.get().strip()
        if not group_id:
            return
        try:
            group_payload = group_config.get_group_config(group_id)
            layer_payload = group_config.get_layer_config(group_id, layer_name)
        except Exception as error:
            self.status_var.set(str(error))
            return
        if layer_payload.get("type", "image") != "text":
            return
        self.fill_group_config_form_from_layer_payload(group_id, group_payload, layer_payload)
        self.status_var.set(f"Editing text layer: {group_id}.{layer_name}")

    def select_new_text_layer(self):
        group_id = self.group_id_var.get().strip()
        group_payload = {}
        if group_id:
            try:
                group_payload = group_config.get_group_config(group_id)
            except Exception:
                group_payload = {}
        layer_name = self.create_next_text_layer_name(group_payload)
        self.text_layer_choice_var.set("")
        self.layer_name_var.set(layer_name)
        self.text_value_var.set("")
        self.text_key_var.set("")
        self.text_height_var.set("0")
        self.text_width_var.set("0")
        self.text_fit_mode_var.set("contain")
        self.layer_x_var.set("0")
        self.layer_y_var.set("0")
        self.layer_scale_w_var.set("100")
        self.layer_scale_h_var.set("100")
        self.status_var.set(f"New text layer: {layer_name}")

    def save_create_group_builder(self):
        group_id = self.group_id_var.get().strip()
        if not group_id:
            messagebox.showerror("Create Group error", "Group id is required")
            return
        try:
            _group, group_report = self.save_current_group_metadata()
            layer = self.build_current_layer_draft()
            if layer:
                if layer["type"] == "text":
                    self.sync_hex_color_to_rgb()
                    if self.safe_int(self.text_width_var.get()) <= 0:
                        self.text_width_var.set(str(max(1, self.safe_int(self.group_rect_w_var.get(), 1))))
                    updates = self.collect_text_layer_updates()
                    updates["height"] = layer["height"]
                    updates["scale_percent"] = layer["scale_percent"]
                    _layer, layer_report = self.service.set_group_config_text_layer(group_id, layer["name"], updates)
                else:
                    if not layer.get("resource_key"):
                        raise ValueError("Graphic resource is required")
                    _layer = group_config.upsert_layer(group_id, layer)
                    layer_report = OperationReport("Group Config Graphic Layer")
                    layer_report.add(f"group: {group_id}")
                    layer_report.add(f"layer: {layer['name']}")
                    layer_report.add(f"resource_key: {layer['resource_key']}")
                self.rebuild_rm_manifest_after_group_change()
                report_text = f"{group_report.to_text()}\n\n{layer_report.to_text()}"
            else:
                self.rebuild_rm_manifest_after_group_change()
                report_text = group_report.to_text()
        except Exception as error:
            self.status_var.set("group was not saved")
            self.show_output(str(error))
            messagebox.showerror("Create Group error", str(error))
            return
        self.reload_index()
        self.refresh_group_editor_layers_from_current_group()
        self.update_group_config_preview()
        self.status_var.set("group saved")
        self.show_output(report_text)

    @staticmethod
    def safe_int(value, default=0):
        try:
            return int(str(value).strip() or default)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def parse_hex_color(value):
        color = str(value or "").strip().lstrip("#")
        if len(color) != 6:
            return (255, 255, 255)
        try:
            return tuple(int(color[index : index + 2], 16) for index in (0, 2, 4))
        except ValueError:
            return (255, 255, 255)

    def sync_hex_color_to_rgb(self):
        red, green, blue = self.parse_hex_color(self.font_color_hex_var.get())
        self.font_color_r_var.set(str(red))
        self.font_color_g_var.set(str(green))
        self.font_color_b_var.set(str(blue))

    def on_builder_font_selected(self, _event=None):
        font_path = self.font_path_var.get().strip()
        self.font_name_var.set(os.path.splitext(os.path.basename(font_path))[0] if font_path else "")
        self.update_group_config_preview()

    def create_right_panel(self, parent):
        right_panel = ttk.Frame(parent, padding=14)
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1)
        parent.add(right_panel, weight=2)

        ttk.Label(right_panel, textvariable=self.right_title_var, style="Heading.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 12)
        )
        self.workbench_container = ttk.Frame(right_panel)
        self.workbench_container.grid(row=1, column=0, sticky="nsew")
        self.workbench_container.rowconfigure(0, weight=1)
        self.workbench_container.columnconfigure(0, weight=1)
        self.workbench_frames = {}
        self.create_png_workbench(self.workbench_container)
        self.create_rm_manifest_workbench(self.workbench_container)
        self.create_create_group_workbench(self.workbench_container)
        self.create_gui_manifest_workbench(self.workbench_container)
        self.create_group_config_workbench(self.workbench_container)

        ttk.Label(right_panel, textvariable=self.status_var, style="Muted.TLabel").grid(
            row=2, column=0, sticky="w", pady=(12, 0)
        )
        self.output_text = tk.Text(
            right_panel,
            height=6,
            bg=self.COLORS["panel_bg"],
            fg=self.COLORS["text"],
            insertbackground=self.COLORS["text"],
            font=("Cascadia Mono", 10),
            relief="flat",
            wrap="none",
            padx=12,
            pady=10,
        )
        self.output_text.grid(row=4, column=0, sticky="ew")
        self.output_text.configure(state="disabled")
        self.output_text.grid_remove()
        self.show_png_workbench()

    def create_png_workbench(self, parent):
        frame = ttk.Frame(parent)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.workbench_frames["png"] = frame

        self.png_workbench_tabs = ttk.Notebook(frame)
        self.png_workbench_tabs.grid(row=0, column=0, sticky="nsew")

        png_preview_tab = ttk.Frame(self.png_workbench_tabs, padding=(0, 8, 0, 0))
        png_preview_tab.columnconfigure(0, weight=1)
        png_preview_tab.rowconfigure(0, weight=1)
        self.png_workbench_tabs.add(png_preview_tab, text="PNG Preview")

        png_manifest_tab = ttk.Frame(self.png_workbench_tabs, padding=(0, 8, 0, 0))
        png_manifest_tab.columnconfigure(0, weight=1)
        png_manifest_tab.rowconfigure(0, weight=1)
        self.png_workbench_tabs.add(png_manifest_tab, text="RM Manifest")

        self.preview_label = tk.Label(
            png_preview_tab,
            bg=self.COLORS["preview_bg"],
            fg=self.COLORS["muted_text"],
            text="Select a PNG resource",
            compound="center",
        )
        self.preview_label.grid(row=0, column=0, sticky="nsew")

        self.create_metadata_editor(png_preview_tab, row=1, column=0)
        self.png_add_to_manifest_button = ttk.Button(
            png_preview_tab,
            text="Add to RM Manifest",
            command=self.add_selected_png_to_rm_manifest,
            style="Primary.TButton",
        )
        self.png_add_to_manifest_button.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self.png_add_to_manifest_button.grid_remove()
        self.create_png_manifest_tree(png_manifest_tab)
        self.png_workbench_tabs.select(png_preview_tab)

    def create_rm_manifest_workbench(self, parent):
        frame = ttk.Frame(parent)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.workbench_frames["rm"] = frame
        self.create_manifest_tree(frame)
        actions = ttk.Frame(frame)
        actions.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        actions.columnconfigure(0, weight=1)
        ttk.Button(actions, text="Add to layer", command=self.add_rm_resource_to_graphic_layer).grid(
            row=0, column=0, sticky="ew"
        )
        self.create_rm_metadata_view(frame)

    def create_rm_metadata_view(self, parent):
        view = ttk.LabelFrame(parent, text="Selected PNG metadata", padding=8)
        view.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        view.columnconfigure(1, weight=1)
        ttk.Label(view, text="resource_key").grid(row=0, column=0, sticky="w", pady=(0, 4))
        ttk.Label(view, textvariable=self.resource_key_var).grid(row=0, column=1, sticky="w", pady=(0, 4))
        ttk.Label(view, text="path").grid(row=1, column=0, sticky="w", pady=(0, 4))
        ttk.Label(view, textvariable=self.path_var).grid(row=1, column=1, sticky="w", pady=(0, 4))
        ttk.Label(view, text="png_size").grid(row=2, column=0, sticky="w", pady=(0, 4))
        ttk.Label(view, textvariable=self.png_size_var).grid(row=2, column=1, sticky="w", pady=(0, 4))
        ttk.Label(view, text="metadata").grid(row=3, column=0, sticky="w", pady=(0, 4))
        ttk.Label(view, textvariable=self.details_var, wraplength=620).grid(row=3, column=1, sticky="w", pady=(0, 4))

    def create_group_config_workbench(self, parent):
        frame = ttk.Frame(parent)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.workbench_frames["group"] = frame
        self.create_group_config_tree(frame)
        actions = ttk.Frame(frame)
        actions.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        ttk.Button(actions, text="EDIT", command=self.edit_selected_group_config).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        ttk.Button(actions, text="DELETE", command=self.delete_selected_group_config, style="Danger.TButton").grid(
            row=0, column=1, sticky="ew", padx=(4, 0)
        )

    def create_gui_manifest_workbench(self, parent):
        frame = ttk.Frame(parent)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.workbench_frames["gui_manifest"] = frame

        self.gui_manifest_tree = ttk.Treeview(
            frame,
            columns=("type", "value"),
            show="tree headings",
            height=16,
        )
        self.gui_manifest_tree.heading("#0", text="GUI object")
        self.gui_manifest_tree.heading("type", text="Type")
        self.gui_manifest_tree.heading("value", text="Value")
        self.gui_manifest_tree.column("#0", width=240)
        self.gui_manifest_tree.column("type", width=90, anchor="center")
        self.gui_manifest_tree.column("value", width=320)
        self.gui_manifest_tree.grid(row=0, column=0, sticky="nsew")
        self.gui_manifest_tree.bind("<<TreeviewSelect>>", self.on_gui_manifest_select)

        tree_scroll = ttk.Scrollbar(frame, orient="vertical", command=self.gui_manifest_tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.gui_manifest_tree.configure(yscrollcommand=tree_scroll.set)

        actions = ttk.Frame(frame)
        actions.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        actions.columnconfigure(0, weight=1)
        ttk.Button(actions, text="EDIT", command=self.edit_selected_gui_manifest_group).grid(
            row=0, column=0, sticky="ew"
        )

    def create_create_group_workbench(self, parent):
        frame = ttk.Frame(parent)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)
        self.workbench_frames["create_group"] = frame
        ttk.Label(frame, text="Group Config Preview").grid(row=0, column=0, sticky="nw", pady=(0, 6))
        preview_frame = ttk.Frame(frame, style="Panel.TFrame")
        preview_frame.grid(row=1, column=0, sticky="nsew")
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        self.group_config_preview_text = tk.Text(
            preview_frame,
            bg=self.COLORS["panel_bg"],
            fg=self.COLORS["text"],
            insertbackground=self.COLORS["text"],
            font=("Cascadia Mono", 10),
            relief="flat",
            wrap="none",
            padx=12,
            pady=10,
        )
        self.group_config_preview_text.grid(row=0, column=0, sticky="nsew")
        preview_y = ttk.Scrollbar(preview_frame, orient="vertical", command=self.group_config_preview_text.yview)
        preview_y.grid(row=0, column=1, sticky="ns")
        preview_x = ttk.Scrollbar(preview_frame, orient="horizontal", command=self.group_config_preview_text.xview)
        preview_x.grid(row=1, column=0, sticky="ew")
        self.group_config_preview_text.configure(yscrollcommand=preview_y.set, xscrollcommand=preview_x.set)
        self.group_config_preview_text.configure(state="disabled")
        self.update_group_config_preview()

    def show_workbench(self, name, title):
        self.right_title_var.set(title)
        self.workbench_frames[name].tkraise()
        self.hide_details_output()

    def show_png_workbench(self):
        self.show_workbench("png", "PNG Workbench")
        self.update_png_manifest_button_visibility()
        if self.selected_asset is None:
            self.status_var.set("")

    def update_png_manifest_button_visibility(self):
        if not hasattr(self, "png_add_to_manifest_button"):
            return
        if self.selected_asset is not None:
            self.png_add_to_manifest_button.grid()
        else:
            self.png_add_to_manifest_button.grid_remove()

    def show_rm_manifest_workbench(self):
        self.show_workbench("rm", "RM Manifest Explorer")

    def show_group_config_workbench(self):
        self.show_workbench("group", "Group Config Explorer")

    def show_gui_manifest_workbench(self):
        self.show_workbench("gui_manifest", "GUI Manifest Explorer")

    def on_mode_tab_changed(self, _event=None):
        if not hasattr(self, "workbench_frames"):
            return
        selected = self.mode_tabs.select()
        if selected == str(self.png_data_tab):
            self.show_png_workbench()
        elif selected == str(self.check_rm_tab):
            self.show_rm_manifest_workbench()
        elif selected == str(self.create_group_tab):
            self.show_workbench("create_group", "Create Group")
        else:
            if self.edit_group_active:
                self.show_workbench("create_group", "Group Config Preview")
            else:
                self.show_gui_manifest_workbench()
        self.update_result_label()

    def reload_index(self):
        selected_resource_key = self.selected_asset.resource_key if self.selected_asset is not None else ""
        open_folders = self.get_open_png_folders()
        if self.rm_manifest_loaded:
            self.manifest = self.service.load_manifest_if_exists()
        else:
            self.manifest = {"resources": {}}
        self.gui_manifest = self.service.load_gui_manifest_if_exists()
        self.png_assets = self.service.load_png_assets()
        self.png_assets_by_key = {asset.resource_key: asset for asset in self.png_assets}
        self.graphics_entries = self.service.load_graphics_entries(assets_by_key=self.png_assets_by_key, manifest=self.manifest)
        self.visible_png_assets = self.filter_png_assets()
        self.visible_graphics_entries = self.filter_graphics_entries()
        self.populate_png_tree(self.visible_png_assets)
        self.restore_open_png_folders(open_folders)
        self.populate_group_config_tree(self.graphics_entries)
        self.populate_manifest_tree(self.visible_graphics_entries)
        if hasattr(self, "gui_manifest_tree"):
            self.populate_gui_manifest_tree()
        if selected_resource_key:
            self.reselect_asset(selected_resource_key, show=False)
        self.update_result_label()

    def populate_png_tree(self, assets):
        self.png_tree.delete(*self.png_tree.get_children())
        self.png_assets_by_item = {}
        self.png_folder_items = {}
        query_is_active = bool(self.search_var.get().strip())

        for asset in assets:
            parent_id = self.ensure_png_folder_path(asset.relative_path)
            frame_size = self.format_frame_size(asset)
            item_id = self.png_tree.insert(
                parent_id,
                "end",
                text=asset.file_name,
                values=(f"{asset.size[0]}x{asset.size[1]}",),
            )
            self.png_assets_by_item[item_id] = asset

        if query_is_active:
            for item_id in self.png_folder_items.values():
                self.png_tree.item(item_id, open=True)

    def get_open_png_folders(self):
        if not hasattr(self, "png_folder_items"):
            return set()
        return {
            folder_key
            for folder_key, item_id in self.png_folder_items.items()
            if self.png_tree.exists(item_id) and self.png_tree.item(item_id, "open")
        }

    def restore_open_png_folders(self, folder_keys):
        for folder_key in folder_keys:
            item_id = self.png_folder_items.get(folder_key)
            if item_id:
                self.png_tree.item(item_id, open=True)

    @staticmethod
    def format_frame_size(asset):
        frame_width, frame_height = asset.manifest_frame_size
        suffix = " !" if asset.metadata.warnings else ""
        return f"{frame_width}x{frame_height}{suffix}"

    def populate_group_config_tree(self, entries):
        self.group_config_tree.delete(*self.group_config_tree.get_children())
        self.group_config_nav_by_item = {}
        query_is_active = bool(self.search_var.get().strip())
        tokens = self.search_var.get().strip().lower().split()
        entry_by_group_layer = {
            (entry.group_file, entry.local_name): entry
            for entry in entries
        }

        group_config.reload_group_config()
        for group_id in group_config.iter_group_ids():
            group_payload = group_config.get_group_config(group_id)
            layers = group_payload.get("layers", ())
            group_matches = self.group_config_group_matches_query(group_id, group_payload, tokens)
            visible_layers = [
                layer
                for layer in layers
                if group_matches or self.group_config_layer_matches_query(group_id, group_payload, layer, tokens)
            ]
            if tokens and not group_matches and not visible_layers:
                continue

            group_item = self.group_config_tree.insert(
                "",
                "end",
                text=group_id,
                values=("group", group_payload.get("role", "")),
                open=query_is_active or group_matches,
            )
            self.group_config_nav_by_item[group_item] = ("group", group_id, group_payload, None, None)

            for layer in visible_layers:
                layer_name = layer.get("name", "")
                layer_type = layer.get("type", "image")
                value = layer.get("resource_key") or layer.get("text") or ""
                item_id = self.group_config_tree.insert(
                    group_item,
                    "end",
                    text=layer_name,
                    values=(layer_type, value),
                )
                entry = entry_by_group_layer.get((group_id, layer_name))
                self.group_config_nav_by_item[item_id] = ("layer", group_id, group_payload, layer, entry)

    @staticmethod
    def group_config_group_matches_query(group_id, group_payload, tokens):
        if not tokens:
            return True
        searchable = " ".join(
            str(value).lower()
            for value in (
                group_id,
                group_payload.get("role", ""),
                " ".join(group_payload.get("tags", ())),
            )
        )
        return all(token in searchable for token in tokens)

    @staticmethod
    def group_config_layer_matches_query(group_id, group_payload, layer, tokens):
        if not tokens:
            return True
        target_ids = [
            target_id
            for target_id, target_payload in group_payload.get("manifest_targets", {}).items()
            if target_payload.get("layer") == layer.get("name")
        ]
        searchable = " ".join(
            str(value).lower()
            for value in (
                group_id,
                group_payload.get("role", ""),
                layer.get("name", ""),
                layer.get("type", "image"),
                layer.get("resource_key", ""),
                layer.get("text", ""),
                " ".join(target_ids),
            )
        )
        return all(token in searchable for token in tokens)

    def populate_manifest_tree_widget(self, tree, item_map):
        tree.delete(*tree.get_children())
        item_map.clear()
        query = self.search_var.get().strip().lower()
        tokens = query.split()

        for resource_key, payload in sorted(self.manifest.get("resources", {}).items()):
            path = payload.get("path", "")
            searchable = f"{resource_key} {path}".lower()
            if tokens and not all(token in searchable for token in tokens):
                continue
            frame = f"{payload.get('frame_width', '')}x{payload.get('frame_height', '')}"
            asset = self.find_png_asset_for_manifest_resource(resource_key, payload)
            if asset is None:
                metadata_status = "missing PNG"
            elif asset.metadata.warnings:
                metadata_status = "missing"
            else:
                metadata_status = "OK"
            item_id = tree.insert(
                "",
                "end",
                text=resource_key,
                values=(path, frame, metadata_status),
            )
            item_map[item_id] = (resource_key, payload)

    def populate_manifest_tree(self, entries):
        self.populate_manifest_tree_widget(self.manifest_tree, self.rm_resource_by_item)
        if hasattr(self, "png_manifest_tree"):
            self.populate_manifest_tree_widget(self.png_manifest_tree, self.png_rm_resource_by_item)

    def populate_gui_manifest_tree(self):
        self.gui_manifest_tree.delete(*self.gui_manifest_tree.get_children())
        self.gui_manifest_nav_by_item = {}
        query = self.search_var.get().strip().lower()
        tokens = query.split()
        query_is_active = bool(tokens)

        manifest = self.gui_manifest or self.service.empty_gui_manifest()
        screens_root = self.gui_manifest_tree.insert("", "end", text="screens", values=("section", ""), open=True)
        frames_root = self.gui_manifest_tree.insert("", "end", text="frames", values=("section", ""), open=query_is_active)
        groups_root = self.gui_manifest_tree.insert("", "end", text="groups", values=("section", ""), open=True)

        for screen_id, payload in sorted(manifest.get("screens", {}).items()):
            if not self.gui_manifest_object_matches(screen_id, payload, tokens):
                continue
            item_id = self.gui_manifest_tree.insert(
                screens_root,
                "end",
                text=screen_id,
                values=("screen", payload.get("class", "")),
                open=query_is_active,
            )
            self.gui_manifest_nav_by_item[item_id] = ("screen", screen_id, payload)

        for frame_id, payload in sorted(manifest.get("frames", {}).items()):
            if not self.gui_manifest_object_matches(frame_id, payload, tokens):
                continue
            item_id = self.gui_manifest_tree.insert(
                frames_root,
                "end",
                text=frame_id,
                values=("frame", ",".join(payload.get("group_ids", ()))),
                open=query_is_active,
            )
            self.gui_manifest_nav_by_item[item_id] = ("frame", frame_id, payload)

        for group_id, payload in sorted(manifest.get("groups", {}).items()):
            if not self.gui_manifest_object_matches(group_id, payload, tokens):
                continue
            group_item = self.gui_manifest_tree.insert(
                groups_root,
                "end",
                text=group_id,
                values=("group", payload.get("role", "")),
                open=query_is_active,
            )
            self.gui_manifest_nav_by_item[group_item] = ("group", group_id, payload)
            for layer_name in payload.get("layer_order", payload.get("layers", {})):
                layer_payload = payload.get("layers", {}).get(layer_name, {})
                layer_item = self.gui_manifest_tree.insert(
                    group_item,
                    "end",
                    text=layer_name,
                    values=("layer", layer_payload.get("resource_key") or layer_payload.get("text", "")),
                )
                self.gui_manifest_nav_by_item[layer_item] = ("layer", group_id, layer_payload)

    @staticmethod
    def gui_manifest_object_matches(object_id, payload, tokens):
        if not tokens:
            return True
        searchable = f"{object_id} {json.dumps(payload, ensure_ascii=False)}".lower()
        return all(token in searchable for token in tokens)

    def find_png_asset_for_manifest_resource(self, resource_key, payload):
        asset = self.png_assets_by_key.get(resource_key)
        if asset is not None:
            return asset
        path = str(payload.get("path", "")).replace("\\", "/")
        for candidate in self.png_assets:
            if candidate.relative_path.replace("\\", "/") == path:
                return candidate
        return None

    def ensure_png_folder_path(self, relative_path):
        parent_id = ""
        folder_parts = os.path.dirname(relative_path).replace("\\", "/").split("/")
        current_path = []
        for folder_name in folder_parts:
            if not folder_name:
                continue
            current_path.append(folder_name)
            folder_key = "/".join(current_path)
            if folder_key not in self.png_folder_items:
                self.png_folder_items[folder_key] = self.png_tree.insert(
                    parent_id,
                    "end",
                    text=folder_name,
                    values=("folder",),
                    open=False,
                )
            parent_id = self.png_folder_items[folder_key]
        return parent_id

    def on_search(self, *_args):
        self.visible_png_assets = self.filter_png_assets()
        self.visible_graphics_entries = self.filter_graphics_entries()
        self.clear_selection(clear_output=False)
        self.populate_png_tree(self.visible_png_assets)
        self.populate_group_config_tree(self.graphics_entries)
        self.populate_manifest_tree(self.visible_graphics_entries)
        if hasattr(self, "gui_manifest_tree"):
            self.populate_gui_manifest_tree()
        self.update_result_label()

    def filter_png_assets(self):
        query = self.search_var.get().strip().lower()
        if not query:
            return self.png_assets[:]
        tokens = query.split()
        return [
            asset
            for asset in self.png_assets
            if all(token in self.png_search_name(asset) for token in tokens)
        ]

    def filter_graphics_entries(self):
        query = self.search_var.get().strip().lower()
        if not query:
            return self.graphics_entries[:]
        tokens = query.split()
        return [
            entry
            for entry in self.graphics_entries
            if all(token in self.graphic_search_name(entry) for token in tokens)
        ]

    @staticmethod
    def png_search_name(asset):
        return os.path.splitext(asset.file_name)[0].lower()

    @staticmethod
    def graphic_search_name(entry):
        if entry.asset is not None:
            return os.path.splitext(entry.asset.file_name)[0].lower()
        return entry.local_name.lower()

    def clear_search(self):
        self.search_var.set("")

    def update_result_label(self):
        query = self.search_var.get().strip()
        if hasattr(self, "mode_tabs"):
            selected = self.mode_tabs.select()
        else:
            selected = ""
        if selected == str(getattr(self, "check_rm_tab", "")):
            total = len(self.manifest.get("resources", {}))
            visible = len(self.manifest_tree.get_children()) if hasattr(self, "manifest_tree") else total
            noun = "RM resources"
        elif selected == str(getattr(self, "edit_group_tab", "")):
            total = len(self.gui_manifest.get("groups", {}))
            visible = len(self.gui_manifest_nav_by_item) if hasattr(self, "gui_manifest_tree") else total
            noun = "GUI Manifest objects"
        elif selected == str(getattr(self, "create_group_tab", "")):
            total = len(self.graphics_entries)
            visible = len(self.visible_graphics_entries)
            noun = "group layers"
        else:
            total = len(self.png_assets)
            visible = len(self.visible_png_assets)
            noun = "PNG resources"
        self.result_var.set(f"Found: {visible} / {total} {noun}" if query else f"{total} {noun}")

    def on_png_select(self, _event):
        selection = self.png_tree.selection()
        if not selection:
            return
        self.show_png_workbench()
        item_id = selection[0]
        if item_id not in self.png_assets_by_item:
            self.clear_selection(clear_output=False)
            return
        self.selected_asset = self.png_assets_by_item[item_id]
        self.selected_graphic = None
        self.group_mode_var.set("Mode: Create")
        self.layer_type_var.set("Graphic")
        self.clear_text_layer_editor()
        self.show_asset(self.selected_asset)

    def on_manifest_select(self, _event):
        selection = self.manifest_tree.selection()
        if not selection:
            return
        item_id = selection[0]
        if item_id not in self.rm_resource_by_item:
            self.clear_selection(clear_output=False)
            return
        resource_key, payload = self.rm_resource_by_item[item_id]
        self.selected_manifest_resource_key = resource_key
        asset = self.find_png_asset_for_manifest_resource(resource_key, payload)
        if asset is not None:
            self.selected_asset = asset
            self.show_asset(asset)
            self.rm_metadata_editor_holder.grid_remove()
            self.status_var.set(f"RM resource selected: {resource_key}")
        else:
            self.selected_asset = None
            self.clear_metadata_fields()
            self.resource_key_var.set(resource_key)
            self.path_var.set(payload.get("path", ""))
            self.details_var.set("PNG file is missing")
            self.status_var.set(f"RM resource selected, PNG missing: {resource_key}")
        self.show_output(self.service.format_gui_object_details("rm_resource", resource_key, payload))

    def on_png_manifest_select(self, _event):
        selection = self.png_manifest_tree.selection()
        if not selection:
            return
        item_id = selection[0]
        if item_id not in self.png_rm_resource_by_item:
            self.clear_selection(clear_output=False)
            return
        resource_key, payload = self.png_rm_resource_by_item[item_id]
        self.selected_manifest_resource_key = resource_key
        asset = self.find_png_asset_for_manifest_resource(resource_key, payload)
        if asset is not None:
            self.selected_asset = asset
            self.show_asset(asset)
            self.status_var.set(f"RM resource selected: {resource_key}")
        else:
            self.selected_asset = None
            self.clear_metadata_fields()
            self.resource_key_var.set(resource_key)
            self.path_var.set(payload.get("path", ""))
            self.details_var.set("PNG file is missing")
            self.status_var.set(f"RM resource selected, PNG missing: {resource_key}")
        self.show_output(self.service.format_gui_object_details("rm_resource", resource_key, payload))

    def on_gui_manifest_select(self, _event):
        selection = self.gui_manifest_tree.selection()
        if not selection:
            return
        item_id = selection[0]
        if item_id not in self.gui_manifest_nav_by_item:
            self.status_var.set("Select a GUI Manifest object")
            return
        object_type, object_id, payload = self.gui_manifest_nav_by_item[item_id]
        self.status_var.set(f"GUI Manifest {object_type} selected: {object_id}")
        self.show_output(self.service.format_gui_object_details(object_type, object_id, payload))

    def on_group_config_select(self, _event):
        selection = self.group_config_tree.selection()
        if not selection:
            return
        item_id = selection[0]
        if item_id not in self.group_config_nav_by_item:
            self.clear_selection(clear_output=False)
            return

        kind, group_id, group_payload, layer_payload, entry = self.group_config_nav_by_item[item_id]
        if kind == "group":
            self.status_var.set(f"group_config group selected: {group_id}")
            self.show_output(self.service.format_gui_object_details("group_config", group_id, group_payload))
            return

        layer_type = layer_payload.get("type", "image")
        self.status_var.set(f"group_config {layer_type} layer selected")
        self.show_output(self.service.format_gui_object_details(layer_type, layer_payload.get("name", ""), layer_payload))

    def fill_group_config_form_from_group(self, group_id, group_payload):
        self.group_id_var.set(group_id)
        self.layer_name_var.set("")
        self.layer_x_var.set("0")
        self.layer_y_var.set("0")
        self.group_role_var.set(group_payload.get("role", ""))
        self.fill_group_geometry_fields(group_payload)
        self.populate_group_editor_layers(group_id, group_payload)
        self.refresh_graphic_layer_choices(group_payload)
        self.refresh_text_layer_choices(group_payload)
        self.target_id_var.set("")
        self.clear_graphic_resource_key()
        self.group_mode_var.set(f"Mode: Edit group {group_id}")
        self.layer_type_var.set("Graphic")
        self.hide_text_layer_editor()

    def fill_group_config_form_from_layer(self, entry):
        group_payload = group_config.get_group_config(entry.group_file)
        self.group_id_var.set(entry.group_file)
        self.layer_name_var.set(entry.local_name)
        self.layer_x_var.set(str(entry.position[0]))
        self.layer_y_var.set(str(entry.position[1]))
        self.group_role_var.set(group_payload.get("role", ""))
        self.target_id_var.set(self.find_target_for_layer(group_payload, entry.local_name))

    def fill_group_config_form_from_layer_payload(self, group_id, group_payload, layer_payload):
        position = self.service.normalize_layer_position(layer_payload.get("position", (0, 0)))
        layer_name = layer_payload.get("name", "")
        self.group_id_var.set(group_id)
        self.layer_name_var.set(layer_name)
        self.layer_x_var.set(str(position[0]))
        self.layer_y_var.set(str(position[1]))
        self.group_role_var.set(group_payload.get("role", ""))
        self.fill_group_geometry_fields(group_payload)
        self.populate_group_editor_layers(group_id, group_payload, selected_layer_name=layer_name)
        self.refresh_graphic_layer_choices(group_payload, selected_layer_name=layer_name)
        self.refresh_text_layer_choices(group_payload, selected_layer_name=layer_name)
        self.target_id_var.set(self.find_target_for_layer(group_payload, layer_name))
        if layer_payload.get("type", "image") == "image":
            self.layer_type_var.set("Graphic")
            self.set_graphic_resource_key(layer_payload.get("resource_key", ""))
            self.hide_text_layer_editor()
        else:
            self.layer_type_var.set("Text")
            self.layer_name_var.set(layer_name)
            self.fill_text_layer_editor(layer_payload)

    def fill_text_layer_editor(self, layer_payload):
        if not layer_payload or layer_payload.get("type", "image") != "text":
            self.clear_text_layer_editor()
            return

        self.show_text_layer_editor()
        size = layer_payload.get("size", (0, 0))
        width, height = self.service.normalize_layer_position(size)
        style = layer_payload.get("style", {})
        color = style.get("color", (255, 255, 255))
        red, green, blue = self.normalize_rgb(color)

        self.text_value_var.set(layer_payload.get("text", ""))
        self.text_key_var.set(layer_payload.get("text_key", ""))
        self.text_width_var.set(str(width))
        self.text_height_var.set(str(height))
        self.text_fit_mode_var.set(layer_payload.get("fit_mode", "none"))
        self.font_name_var.set(style.get("font_name", "") or "")
        self.font_path_var.set(style.get("font_path", "") or "")
        self.font_size_var.set(str(style.get("font_size", 24)))
        self.font_color_r_var.set(str(red))
        self.font_color_g_var.set(str(green))
        self.font_color_b_var.set(str(blue))
        self.font_antialias_var.set(bool(style.get("antialias", True)))

    def populate_group_editor_layers(self, group_id, group_payload, selected_layer_name=""):
        if not hasattr(self, "group_editor_layers_tree"):
            return
        self.is_populating_group_editor_layers = True
        try:
            self.group_editor_layers_tree.delete(*self.group_editor_layers_tree.get_children())
            self.group_editor_layer_by_item = {}
            selected_item = None
            for layer_payload in group_payload.get("layers", ()):
                layer_name = layer_payload.get("name", "")
                layer_type = layer_payload.get("type", "image")
                value = layer_payload.get("resource_key") or layer_payload.get("text") or ""
                position = self.service.normalize_layer_position(layer_payload.get("position", (0, 0)))
                item_id = self.group_editor_layers_tree.insert(
                    "",
                    "end",
                    text=layer_name,
                    values=(layer_type, value, f"{position[0]}, {position[1]}"),
                )
                self.group_editor_layer_by_item[item_id] = (group_id, group_payload, layer_payload)
                if layer_name == selected_layer_name:
                    selected_item = item_id
            if selected_item:
                self.group_editor_layers_tree.selection_set(selected_item)
                self.group_editor_layers_tree.see(selected_item)
        finally:
            self.is_populating_group_editor_layers = False

    def clear_group_editor_layers(self):
        if not hasattr(self, "group_editor_layers_tree"):
            return
        self.group_editor_layers_tree.delete(*self.group_editor_layers_tree.get_children())
        self.group_editor_layer_by_item = {}

    def refresh_group_editor_layers_from_current_group(self):
        group_id = self.group_id_var.get().strip()
        if not group_id:
            self.clear_group_editor_layers()
            return
        try:
            group_config.reload_group_config()
            group_payload = group_config.get_group_config(group_id)
        except KeyError:
            self.clear_group_editor_layers()
            return
        self.populate_group_editor_layers(group_id, group_payload, selected_layer_name=self.layer_name_var.get().strip())
        self.refresh_graphic_layer_choices(group_payload, selected_layer_name=self.layer_name_var.get().strip())
        self.refresh_text_layer_choices(group_payload, selected_layer_name=self.layer_name_var.get().strip())

    def on_group_editor_layer_select(self, _event):
        if not hasattr(self, "group_editor_layers_tree"):
            return
        if self.is_populating_group_editor_layers:
            return
        selection = self.group_editor_layers_tree.selection()
        if not selection:
            return
        item_id = selection[0]
        if item_id not in self.group_editor_layer_by_item:
            return
        group_id, group_payload, layer_payload = self.group_editor_layer_by_item[item_id]
        self.fill_group_config_form_from_layer_payload(group_id, group_payload, layer_payload)
        self.fill_text_layer_editor(layer_payload)

    def clear_text_layer_editor(self):
        self.text_layer_choice_var.set("")
        self.text_value_var.set("")
        self.text_key_var.set("")
        self.text_width_var.set("0")
        self.text_height_var.set("0")
        self.text_fit_mode_var.set("none")
        self.font_name_var.set("")
        self.font_path_var.set("")
        self.font_size_var.set("24")
        self.font_color_r_var.set("255")
        self.font_color_g_var.set("255")
        self.font_color_b_var.set("255")
        self.font_antialias_var.set(True)
        self.hide_text_layer_editor()

    @staticmethod
    def normalize_rgb(color):
        if isinstance(color, str):
            values = [part.strip() for part in color.split(",")]
        else:
            values = list(color or ())
        values = [int(value) for value in values[:3]]
        while len(values) < 3:
            values.append(255)
        return tuple(max(0, min(255, value)) for value in values)

    @staticmethod
    def find_target_for_layer(group_payload, layer_name):
        for target_id, target_payload in group_payload.get("manifest_targets", {}).items():
            if target_payload.get("layer") == layer_name:
                return target_id
        return ""

    def fill_group_geometry_fields(self, group_payload):
        rect = self.normalize_rect(group_payload.get("rect", (0, 0, 0, 0)))
        hit_rect = self.normalize_rect(group_payload.get("hit_rect", rect))
        self.group_rect_x_var.set(str(rect[0]))
        self.group_rect_y_var.set(str(rect[1]))
        self.group_rect_w_var.set(str(rect[2]))
        self.group_rect_h_var.set(str(rect[3]))
        self.group_hit_x_var.set(str(hit_rect[0]))
        self.group_hit_y_var.set(str(hit_rect[1]))
        self.group_hit_w_var.set(str(hit_rect[2]))
        self.group_hit_h_var.set(str(hit_rect[3]))
        self.group_scale_var.set(str(group_payload.get("scale_factor", 1.0)))
        self.group_hide_rect_var.set(bool(group_payload.get("hide_rect", True)))
        self.group_tags_var.set(", ".join(group_payload.get("tags", ())))

    @staticmethod
    def normalize_rect(rect):
        values = list(rect or (0, 0, 0, 0))
        while len(values) < 4:
            values.append(0)
        return tuple(int(value) for value in values[:4])

    @staticmethod
    def parse_tags(value):
        return [tag.strip() for tag in value.split(",") if tag.strip()]

    def collect_group_metadata(self):
        return {
            "role": self.group_role_var.get().strip(),
            "tags": self.parse_tags(self.group_tags_var.get()),
            "rect": list(
                self.read_rect_vars(
                    (
                        self.group_rect_x_var,
                        self.group_rect_y_var,
                        self.group_rect_w_var,
                        self.group_rect_h_var,
                    ),
                    "Group rect",
                )
            ),
            "hit_rect": list(
                self.read_rect_vars(
                    (
                        self.group_hit_x_var,
                        self.group_hit_y_var,
                        self.group_hit_w_var,
                        self.group_hit_h_var,
                    ),
                    "Group hit_rect",
                )
            ),
            "scale_factor": self.read_float_var(self.group_scale_var, "Group scale", default=1.0, min_value=0.01),
            "hide_rect": bool(self.group_hide_rect_var.get()),
        }

    @staticmethod
    def _read_var_text(variable):
        return str(variable.get()).strip()

    def read_int_var(self, variable, field_name, default=0, min_value=None):
        text = self._read_var_text(variable)
        if not text:
            value = default
        else:
            try:
                value = int(text)
            except ValueError as error:
                raise ValueError(f"{field_name} must be an integer") from error
        if min_value is not None and value < min_value:
            raise ValueError(f"{field_name} must be >= {min_value}")
        return value

    def read_float_var(self, variable, field_name, default=0.0, min_value=None):
        text = self._read_var_text(variable)
        if not text:
            value = default
        else:
            try:
                value = float(text)
            except ValueError as error:
                raise ValueError(f"{field_name} must be a number") from error
        if min_value is not None and value < min_value:
            raise ValueError(f"{field_name} must be >= {min_value}")
        return value

    def read_position_vars(self, x_var, y_var, field_name="Position"):
        return (
            self.read_int_var(x_var, f"{field_name} X"),
            self.read_int_var(y_var, f"{field_name} Y"),
        )

    def read_rect_vars(self, variables, field_name):
        x_var, y_var, width_var, height_var = variables
        return (
            self.read_int_var(x_var, f"{field_name} X"),
            self.read_int_var(y_var, f"{field_name} Y"),
            self.read_int_var(width_var, f"{field_name} width", min_value=0),
            self.read_int_var(height_var, f"{field_name} height", min_value=0),
        )

    def save_current_group_metadata(self):
        group_id = self.group_id_var.get().strip()
        if not group_id:
            raise ValueError("Group id is required")
        return self.service.save_group_config_metadata(
            group_id,
            self.collect_group_metadata(),
            source_group_id=self.group_edit_source_id,
        )

    def clear_selection(self, clear_output=True):
        self.cancel_preview_refresh()
        self.selected_asset = None
        self.selected_graphic = None
        self.preview_asset = None
        self.preview_image = None
        self.preview_label.configure(image="", text="Select a PNG resource")
        self.update_png_manifest_button_visibility()
        self.clear_metadata_fields()
        self.status_var.set("")
        if clear_output:
            self.show_output("")

    def clear_metadata_fields(self):
        self.resource_key_var.set("")
        self.path_var.set("")
        self.png_size_var.set("")
        self.frame_width_var.set("")
        self.frame_height_var.set("")
        self.details_var.set("")

    def show_asset(self, asset, graphic=None):
        self.resource_key_var.set(asset.resource_key)
        self.path_var.set(asset.relative_path)
        self.png_size_var.set(f"{asset.size[0]}x{asset.size[1]}")
        self.frame_width_var.set(str(asset.metadata.frame_width or asset.size[0]))
        self.frame_height_var.set(str(asset.metadata.frame_height or asset.size[1]))

        frame_width, frame_height = asset.manifest_frame_size
        rows = asset.size[1] // frame_height if frame_height else 0
        warning_text = "; ".join(asset.metadata.warnings) if asset.metadata.warnings else "metadata OK"
        self.details_var.set(f"Frame: {frame_width}x{frame_height} | rows: {rows} | {warning_text}")
        self.status_var.set(graphic.status if graphic else "PNG selected")
        self.update_png_manifest_button_visibility()
        self.show_preview(asset)
        if graphic and graphic.warnings:
            self.show_output("\n".join(graphic.warnings))

    def show_preview(self, asset):
        self.preview_asset = asset
        self.root.update_idletasks()
        width = max(1, self.preview_label.winfo_width() - 24)
        height = max(1, self.preview_label.winfo_height() - 24)
        if width <= 1 or height <= 1:
            width, height = self.PREVIEW_SIZE
        try:
            with Image.open(asset.path) as image:
                image = image.convert("RGBA")
                self.draw_frame_grid(image, asset)
                image.thumbnail((width, height))
                self.preview_image = ImageTk.PhotoImage(image)
        except OSError as error:
            self.preview_image = None
            self.preview_label.configure(image="", text="Preview unavailable")
            self.status_var.set(f"Preview unavailable: {error}")
            return
        self.preview_label.configure(image=self.preview_image, text="")

    def refresh_preview_after_layout_change(self):
        if self.preview_asset is not None:
            self.cancel_preview_refresh()
            asset = self.preview_asset
            self.preview_after_id = self.root.after_idle(lambda: self.run_preview_refresh(asset))

    def cancel_preview_refresh(self):
        if self.preview_after_id is None:
            return
        try:
            self.root.after_cancel(self.preview_after_id)
        except tk.TclError:
            pass
        self.preview_after_id = None

    def run_preview_refresh(self, asset):
        self.preview_after_id = None
        if asset is self.preview_asset:
            self.show_preview(asset)

    def show_text_layer_preview(self, layer_payload=None):
        layer_payload = layer_payload or {
            "text": self.text_value_var.get(),
            "size": [
                max(1, self.safe_int(self.text_width_var.get(), 1)),
                max(1, self.safe_int(self.text_height_var.get(), 1)),
            ],
            "fit_mode": self.text_fit_mode_var.get(),
            "style": {
                "font_name": self.font_name_var.get().strip(),
                "font_path": self.font_path_var.get().strip(),
                "font_size": max(1, self.safe_int(self.font_size_var.get(), 24)),
                "color": list(
                    self.normalize_rgb(
                        (
                            self.font_color_r_var.get().strip() or "0",
                            self.font_color_g_var.get().strip() or "0",
                            self.font_color_b_var.get().strip() or "0",
                        )
                    )
                ),
                "antialias": bool(self.font_antialias_var.get()),
            },
        }
        image = self.render_text_layer_preview(layer_payload)
        image.thumbnail(self.PREVIEW_SIZE)
        self.preview_image = ImageTk.PhotoImage(image)
        self.preview_label.configure(image=self.preview_image, text="")

    def render_text_layer_preview(self, layer_payload):
        width, height = self.service.normalize_layer_position(layer_payload.get("size", (320, 80)))
        width = max(1, width)
        height = max(1, height)
        style = layer_payload.get("style", {})
        color = self.normalize_rgb(style.get("color", (255, 255, 255)))
        font = self.load_preview_font(style)
        text = str(layer_payload.get("text", ""))
        text_image = self.render_text_image(text, font, color)
        fitted_text = self.fit_preview_text_image(text_image, (width, height), layer_payload.get("fit_mode", "none"))
        image = Image.new("RGBA", (width, height), (32, 34, 38, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, width - 1, height - 1), outline=(91, 114, 138, 255))
        self.alpha_composite_center(image, fitted_text)
        return image

    def load_preview_font(self, style):
        font_size = int(style.get("font_size", 24) or 24)
        font_path = style.get("font_path")
        if font_path:
            resolved_path = font_path if os.path.isabs(font_path) else os.path.join(PROJECT_DIR, font_path)
            if os.path.exists(resolved_path):
                return ImageFont.truetype(resolved_path, font_size)
        font_name = style.get("font_name")
        if font_name and os.path.exists(font_name):
            return ImageFont.truetype(font_name, font_size)
        try:
            return ImageFont.truetype("arial.ttf", font_size)
        except OSError:
            return ImageFont.load_default()

    @staticmethod
    def render_text_image(text, font, color):
        probe = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        draw = ImageDraw.Draw(probe)
        bbox = draw.textbbox((0, 0), text or " ", font=font)
        width = max(1, bbox[2] - bbox[0])
        height = max(1, bbox[3] - bbox[1])
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.text((-bbox[0], -bbox[1]), text, font=font, fill=(*color, 255))
        return image

    @staticmethod
    def alpha_composite_center(target, source):
        target_x = (target.width - source.width) // 2
        target_y = (target.height - source.height) // 2
        source_x = max(0, -target_x)
        source_y = max(0, -target_y)
        paste_x = max(0, target_x)
        paste_y = max(0, target_y)
        visible_width = min(source.width - source_x, target.width - paste_x)
        visible_height = min(source.height - source_y, target.height - paste_y)
        if visible_width <= 0 or visible_height <= 0:
            return
        cropped_source = source.crop((source_x, source_y, source_x + visible_width, source_y + visible_height))
        target.alpha_composite(cropped_source, (paste_x, paste_y))

    @staticmethod
    def fit_preview_text_image(image, target_size, fit_mode):
        fit_mode = (fit_mode or "none").strip().lower()
        target_width, target_height = target_size
        if fit_mode in ("none", ""):
            return image
        if image.width <= 0 or image.height <= 0:
            return image
        if fit_mode == "width":
            scale = target_width / image.width
            size = (target_width, max(1, round(image.height * scale)))
        elif fit_mode == "height":
            scale = target_height / image.height
            size = (max(1, round(image.width * scale)), target_height)
        elif fit_mode == "contain":
            scale = min(target_width / image.width, target_height / image.height)
            size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
        elif fit_mode == "stretch":
            size = target_size
        else:
            size = image.size
        if size == image.size:
            return image
        resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.BICUBIC)
        return image.resize(size, resampling)

    @staticmethod
    def draw_frame_grid(image, asset):
        frame_width, frame_height = asset.manifest_frame_size
        if frame_width <= 0 or frame_height <= 0:
            return
        draw = ImageDraw.Draw(image)
        width, height = image.size
        for y in range(0, height, frame_height):
            draw.line((0, y, width, y), fill=(255, 0, 0, 180), width=1)
        draw.rectangle((0, 0, min(frame_width, width) - 1, min(frame_height, height) - 1), outline=(255, 220, 0, 220), width=2)

    def get_png_resource(self):
        if self.selected_asset is None:
            self.status_var.set("Select a PNG first")
            return
        text = self.service.create_graphics_snippet(self.selected_asset)
        self.copy_to_clipboard(text)
        self.show_output(text)
        self.status_var.set("group_config layer snippet copied")

    def add_selected_png_to_rm_manifest(self):
        if self.selected_asset is None:
            self.status_var.set("Select a PNG first")
            return
        try:
            manifest_path = ResourceManager.get_manifest_path(self.assets_dir)
            if not os.path.exists(manifest_path):
                manifest, _report = self.service.build_manifest_from_graphics()
                ResourceManager.save_manifest(self.assets_dir, manifest)
            self.manifest, report = self.service.add_png_asset_to_manifest(self.selected_asset)
            self.rm_manifest_loaded = True
        except Exception as error:
            self.status_var.set("PNG was not added to RM Manifest")
            self.show_output(str(error))
            messagebox.showerror("RM Manifest error", str(error))
            return
        self.reload_index()
        self.status_var.set("PNG added to RM Manifest")
        self.show_output(report.to_text())

    def add_rm_resource_to_graphic_layer(self):
        if not self.selected_manifest_resource_key:
            self.status_var.set("Select an RM resource first")
            return
        self.set_graphic_resource_key(self.selected_manifest_resource_key)
        selected_layer_name = self.graphic_layer_choice_var.get().strip()
        if selected_layer_name:
            group_id = self.group_id_var.get().strip()
            if not group_id:
                self.status_var.set("Select a group before updating a layer")
                return
            try:
                layer_payload = group_config.set_layer_resource(
                    group_id,
                    selected_layer_name,
                    self.selected_manifest_resource_key,
                )
                self.rebuild_rm_manifest_after_group_change()
                group_payload = group_config.get_group_config(group_id)
                self.fill_group_config_form_from_layer_payload(group_id, group_payload, layer_payload)
                self.reload_index()
                self.update_group_config_preview()
            except Exception as error:
                self.status_var.set("Layer resource_key was not updated")
                self.show_output(str(error))
                messagebox.showerror("Group Config error", str(error))
                return
            self.status_var.set(
                f"resource_key updated for layer {selected_layer_name}: "
                f"{self.selected_manifest_resource_key}"
            )
            return

        if not self.layer_name_var.get().strip():
            self.layer_name_var.set(self.create_layer_name_from_resource_key(self.selected_manifest_resource_key))
        self.status_var.set(
            f"New layer {self.layer_name_var.get().strip()} resource_key set: "
            f"{self.selected_manifest_resource_key}"
        )

    def edit_manifest_png_metadata(self):
        if self.selected_asset is None:
            self.status_var.set("Select an RM resource with an existing PNG first")
            return
        self.rm_metadata_editor_holder.grid()
        self.show_asset(self.selected_asset)
        self.status_var.set("PNG metadata editor opened")

    def clear_graphic_resource(self):
        self.clear_graphic_resource_key()
        self.selected_manifest_resource_key = None

    def clear_group_config_form(self):
        self.group_edit_source_id = None
        self.edit_group_id = ""
        self.group_id_var.set("")
        self.group_role_var.set("")
        self.group_tags_var.set("")
        self.group_rect_x_var.set("0")
        self.group_rect_y_var.set("0")
        self.group_rect_w_var.set("0")
        self.group_rect_h_var.set("0")
        self.group_hit_x_var.set("0")
        self.group_hit_y_var.set("0")
        self.group_hit_w_var.set("0")
        self.group_hit_h_var.set("0")
        self.group_scale_var.set("1.0")
        self.group_hide_rect_var.set(True)
        self.layer_name_var.set("")
        self.graphic_layer_choice_var.set("")
        self.text_layer_choice_var.set("")
        self.layer_x_var.set("0")
        self.layer_y_var.set("0")
        self.target_id_var.set("")
        self.clear_graphic_resource_key()
        self.refresh_graphic_layer_choices()
        self.refresh_text_layer_choices()
        self.clear_text_layer_editor()
        self.clear_group_editor_layers()
        self.group_mode_var.set("Mode: Create")
        self.layer_type_var.set("Graphic")
        self.show_rm_manifest_workbench()
        self.status_var.set("New group config")

    def rebuild_rm_manifest_after_group_change(self):
        manifest, _report = self.service.build_manifest_from_graphics()
        self.manifest = ResourceManager.save_manifest(self.assets_dir, manifest)
        self.rm_manifest_loaded = True

    def save_group_config_metadata_only(self):
        try:
            _group, report = self.save_current_group_metadata()
            self.rebuild_rm_manifest_after_group_change()
        except Exception as error:
            self.status_var.set("group metadata was not saved")
            self.show_output(str(error))
            messagebox.showerror("Group Config error", str(error))
            return
        self.reload_index()
        self.refresh_group_editor_layers_from_current_group()
        self.show_group_config_workbench()
        self.status_var.set("group metadata saved")
        self.show_output(report.to_text())

    def upsert_group_config_layer(self):
        if self.layer_type_var.get() != "Graphic":
            self.status_var.set("Switch layer type to Graphic to save a graphic layer")
            return
        group_id = self.group_id_var.get().strip()
        layer_name = self.layer_name_var.get().strip()
        resource_key = self.get_graphic_resource_key()
        if not group_id or not layer_name or not resource_key:
            self.status_var.set("Group, layer, and resource are required")
            messagebox.showerror("Group Config error", "Group, layer, and resource are required")
            return

        try:
            _group, group_report = self.save_current_group_metadata()
            position = self.read_position_vars(self.layer_x_var, self.layer_y_var, "Layer position")
            _layer, report = self.service.upsert_group_config_image_layer(
                group_id,
                layer_name,
                resource_key,
                position=position,
                role=self.group_role_var.get().strip(),
                target_id=self.target_id_var.get().strip(),
            )
            self.rebuild_rm_manifest_after_group_change()
        except Exception as error:
            self.status_var.set("group_config was not updated")
            self.show_output(str(error))
            messagebox.showerror("Group Config error", str(error))
            return

        self.reload_index()
        self.refresh_group_editor_layers_from_current_group()
        self.show_rm_manifest_workbench()
        self.status_var.set("group_config layer saved")
        self.show_output(f"{group_report.to_text()}\n\n{report.to_text()}")

    def save_group_config_layer_position(self):
        group_id = self.group_id_var.get().strip()
        layer_name = self.layer_name_var.get().strip()
        if not group_id or not layer_name:
            self.status_var.set("Group and layer are required")
            messagebox.showerror("Group Config error", "Group and layer are required")
            return

        try:
            _group, group_report = self.save_current_group_metadata()
            position = self.read_position_vars(self.layer_x_var, self.layer_y_var, "Layer position")
            _layer, report = self.service.set_group_config_layer_position(
                group_id,
                layer_name,
                position,
            )
            self.rebuild_rm_manifest_after_group_change()
        except Exception as error:
            self.status_var.set("layer position was not updated")
            self.show_output(str(error))
            messagebox.showerror("Group Config error", str(error))
            return

        self.reload_index()
        self.refresh_group_editor_layers_from_current_group()
        self.status_var.set("layer position saved")
        self.show_output(f"{group_report.to_text()}\n\n{report.to_text()}")

    def save_group_config_text_layer(self):
        self.layer_type_var.set("Text")
        group_id = self.group_id_var.get().strip()
        layer_name = self.text_layer_choice_var.get().strip() or self.layer_name_var.get().strip()
        if not group_id or not layer_name:
            self.status_var.set("Group and layer are required")
            messagebox.showerror("Text Layer error", "Group and layer are required")
            return
        self.layer_name_var.set(layer_name)

        try:
            _group, group_report = self.save_current_group_metadata()
            updates = self.collect_text_layer_updates()
            _layer, report = self.service.set_group_config_text_layer(
                group_id,
                layer_name,
                updates,
            )
            self.rebuild_rm_manifest_after_group_change()
        except Exception as error:
            self.status_var.set("text layer was not updated")
            self.show_output(str(error))
            messagebox.showerror("Text Layer error", str(error))
            return

        self.reload_index()
        self.refresh_group_editor_layers_from_current_group()
        self.show_text_layer_preview()
        self.status_var.set("text layer saved")
        self.show_output(f"{group_report.to_text()}\n\n{report.to_text()}")

    def delete_group_config_layer(self):
        group_id = self.group_id_var.get().strip()
        layer_name = self.layer_name_var.get().strip()
        if not group_id or not layer_name:
            self.status_var.set("Group and layer are required")
            messagebox.showerror("Group Config error", "Group and layer are required")
            return
        if not messagebox.askyesno("Delete layer", f"Delete layer '{group_id}.{layer_name}'?"):
            return
        try:
            _removed, report = self.service.delete_group_config_layer(group_id, layer_name)
            self.rebuild_rm_manifest_after_group_change()
        except Exception as error:
            self.status_var.set("layer was not deleted")
            self.show_output(str(error))
            messagebox.showerror("Group Config error", str(error))
            return
        self.layer_name_var.set("")
        self.clear_graphic_resource_key()
        self.clear_text_layer_editor()
        self.reload_index()
        self.refresh_group_editor_layers_from_current_group()
        self.show_group_config_workbench()
        self.status_var.set("layer deleted")
        self.show_output(report.to_text())

    def edit_selected_group_config(self):
        selection = self.group_config_tree.selection()
        if not selection:
            self.status_var.set("Select a group or layer first")
            return
        item_id = selection[0]
        if item_id not in self.group_config_nav_by_item:
            self.status_var.set("Select a group_config item")
            return

        kind, group_id, group_payload, layer_payload, entry = self.group_config_nav_by_item[item_id]
        self.group_edit_source_id = group_id
        if kind == "group":
            self.fill_group_config_form_from_group(group_id, group_payload)
            self.clear_text_layer_editor()
        else:
            self.fill_group_config_form_from_layer_payload(group_id, group_payload, layer_payload)
            self.fill_text_layer_editor(layer_payload)
            if layer_payload.get("type", "image") == "image":
                self.set_graphic_resource_key(layer_payload.get("resource_key", ""))
                self.hide_text_layer_editor()
        self.group_mode_var.set(f"Mode: Edit group {group_id}")
        self.show_rm_manifest_workbench()
        self.status_var.set(f"Editing group_config: {group_id}")
        self.show_output(self.service.format_gui_object_details("group_config", group_id, group_payload))

    def edit_selected_gui_manifest_group(self):
        selection = self.gui_manifest_tree.selection()
        if not selection:
            self.status_var.set("Select a group in GUI Manifest first")
            return
        item_id = selection[0]
        if item_id not in self.gui_manifest_nav_by_item:
            self.status_var.set("Select a GUI Manifest group")
            return

        object_type, object_id, _payload = self.gui_manifest_nav_by_item[item_id]
        group_id = object_id
        if object_type == "layer":
            group_id = object_id
        elif object_type != "group":
            self.status_var.set("Only GUI Manifest groups and layers can be edited")
            return

        try:
            group_config.reload_group_config()
            group_payload = group_config.get_group_config(group_id)
        except Exception as error:
            self.status_var.set(f"group_config missing for GUI Manifest group: {group_id}")
            self.show_output(str(error))
            messagebox.showerror("Edit Group error", str(error))
            return

        self.ensure_edit_group_form()
        self.group_edit_source_id = group_id
        self.edit_group_id = group_id
        layers = group_payload.get("layers", ())
        if layers:
            first_layer = layers[0]
            self.fill_group_config_form_from_layer_payload(group_id, group_payload, first_layer)
            self.fill_text_layer_editor(first_layer)
            if first_layer.get("type", "image") == "image":
                self.set_graphic_resource_key(first_layer.get("resource_key", ""))
                self.hide_text_layer_editor()
        else:
            self.fill_group_config_form_from_group(group_id, group_payload)
            self.clear_text_layer_editor()

        self.edit_group_active = True
        self.edit_group_empty_label.grid_remove()
        self.edit_group_form_holder.grid()
        self.group_builder_sections["edit"]["form"].grid()
        self.set_edit_group_actions_enabled(True)
        self.mode_tabs.select(self.edit_group_tab)
        self.group_mode_var.set(f"Mode: Edit group {group_id}")
        self.show_workbench("create_group", "Group Config Preview")
        self.update_group_config_preview()
        self.status_var.set(f"Editing GUI Manifest group: {group_id}")
        self.show_output(self.service.format_gui_object_details("group_config", group_id, group_payload))

    def ensure_edit_group_form(self):
        if "edit" in self.group_builder_sections:
            return
        self.create_group_builder(
            self.edit_group_form_holder,
            builder_key="edit",
            show_cancel=True,
        )

    def cancel_edit_group(self):
        self.edit_group_active = False
        self.clear_group_config_form()
        self.edit_group_form_holder.grid_remove()
        self.edit_group_empty_label.grid()
        self.set_edit_group_actions_enabled(False)
        self.show_gui_manifest_workbench()
        self.status_var.set("Edit group cancelled")

    def set_edit_group_actions_enabled(self, enabled):
        if not hasattr(self, "edit_group_save_button"):
            return
        state = ["!disabled"] if enabled else ["disabled"]
        self.edit_group_save_button.state(state)
        self.edit_group_cancel_button.state(state)

    def build_update_gui_manifest(self):
        try:
            manifest, report = self.service.update_gui_manifest()
            self.service.save_gui_manifest(manifest)
            self.gui_manifest = manifest
        except Exception as error:
            self.status_var.set("GUI Manifest was not updated")
            self.show_output(str(error))
            messagebox.showerror("GUI Manifest error", str(error))
            return

        if hasattr(self, "gui_manifest_tree"):
            self.populate_gui_manifest_tree()
        self.status_var.set("GUI Manifest built/updated")
        self.show_output(report.to_text())

    def build_groups(self):
        try:
            _group_store, report = self.service.build_groups_from_config()
        except Exception as error:
            self.status_var.set("Groups were not built")
            self.show_output(str(error))
            messagebox.showerror("Build Groups error", str(error))
            return

        group_config.reload_group_config()
        self.reload_index()
        self.update_group_config_preview()
        self.status_var.set("Groups built from group_config.json")
        self.show_output(report.to_text())

    def delete_selected_group_config(self):
        selection = self.group_config_tree.selection()
        if not selection:
            self.status_var.set("Select a group first")
            return
        item_id = selection[0]
        if item_id not in self.group_config_nav_by_item:
            self.status_var.set("Select a group_config item")
            return
        _kind, group_id, _group_payload, _layer_payload, _entry = self.group_config_nav_by_item[item_id]
        if not messagebox.askyesno("Delete group", f"Delete group_config group '{group_id}'?"):
            return
        try:
            group_config.delete_group(group_id)
            self.rebuild_rm_manifest_after_group_change()
        except Exception as error:
            self.status_var.set("group_config group was not deleted")
            self.show_output(str(error))
            messagebox.showerror("Group Config error", str(error))
            return
        self.clear_group_config_form()
        self.reload_index()
        self.show_group_config_workbench()
        self.status_var.set(f"group_config group deleted: {group_id}")

    def collect_text_layer_updates(self):
        text_key = self.text_key_var.get().strip()
        font_name = self.font_name_var.get().strip()
        font_path = self.font_path_var.get().strip()
        size = (
            self.read_int_var(self.text_width_var, "Text width", min_value=0),
            self.read_int_var(self.text_height_var, "Text height", min_value=0),
        )
        color = self.normalize_rgb(
            (
                self.font_color_r_var.get().strip() or "0",
                self.font_color_g_var.get().strip() or "0",
                self.font_color_b_var.get().strip() or "0",
            )
        )
        style = {
            "font_size": self.read_int_var(self.font_size_var, "Font size", default=24, min_value=1),
            "color": list(color),
            "antialias": bool(self.font_antialias_var.get()),
        }
        if font_name:
            style["font_name"] = font_name
        else:
            style["font_name"] = None
        if font_path:
            style["font_path"] = font_path
        else:
            style["font_path"] = None

        return {
            "text": self.text_value_var.get(),
            "text_key": text_key or None,
            "size": [max(1, size[0]), max(1, size[1])],
            "position": [
                self.read_int_var(self.layer_x_var, "Layer position X"),
                self.read_int_var(self.layer_y_var, "Layer position Y"),
            ],
            "fit_mode": self.text_fit_mode_var.get().strip() or "none",
            "style": style,
        }

    def browse_text_font_path(self):
        file_path = filedialog.askopenfilename(
            title="Select font file",
            filetypes=(("Font files", "*.ttf *.otf"), ("All files", "*.*")),
            initialdir=os.path.join(PROJECT_DIR, "assets", "fonts"),
        )
        if not file_path:
            return
        self.font_path_var.set(self.to_project_relative_path(file_path))

    def pick_text_color(self):
        color = self.normalize_rgb(
            (
                self.font_color_r_var.get().strip() or "0",
                self.font_color_g_var.get().strip() or "0",
                self.font_color_b_var.get().strip() or "0",
            )
        )
        selected, _hex = colorchooser.askcolor(color=color, title="Select text color")
        if not selected:
            return
        red, green, blue = (round(value) for value in selected)
        self.font_color_r_var.set(str(red))
        self.font_color_g_var.set(str(green))
        self.font_color_b_var.set(str(blue))

    @staticmethod
    def to_project_relative_path(file_path):
        try:
            return os.path.relpath(file_path, PROJECT_DIR).replace("\\", "/")
        except ValueError:
            return file_path.replace("\\", "/")

    def save_png_metadata(self):
        if self.selected_asset is None:
            self.status_var.set("Select a PNG first")
            return
        try:
            frame_width = self.read_int_var(self.frame_width_var, "Frame width", min_value=1)
            frame_height = self.read_int_var(self.frame_height_var, "Frame height", min_value=1)
            self.service.write_png_metadata(self.selected_asset.path, frame_width, frame_height)
        except Exception as error:
            self.status_var.set("PNG metadata was not saved")
            self.show_output(str(error))
            messagebox.showerror("PNG metadata error", str(error))
            return

        selected_key = self.selected_asset.resource_key
        self.reload_index()
        self.reselect_asset(selected_key)
        self.status_var.set("PNG metadata saved")
        self.show_output(f"Saved PNG metadata for {selected_key}: {frame_width}x{frame_height}")

    def reselect_asset(self, resource_key, show=True):
        for item_id, asset in self.png_assets_by_item.items():
            if asset.resource_key == resource_key:
                parent_id = self.png_tree.parent(item_id)
                while parent_id:
                    self.png_tree.item(parent_id, open=True)
                    parent_id = self.png_tree.parent(parent_id)
                self.png_tree.selection_set(item_id)
                self.png_tree.see(item_id)
                self.selected_asset = asset
                if show:
                    self.show_asset(asset)
                return

    def build_manifest(self):
        selected_key = self.selected_asset.resource_key if self.selected_asset is not None else ""
        manifest, report = self.service.build_manifest_from_graphics()
        ResourceManager.save_manifest(self.assets_dir, manifest)
        self.rm_manifest_loaded = True
        self.reload_index()
        if selected_key:
            self.reselect_asset(selected_key)
        self.show_output(report.to_text())
        self.refresh_preview_after_layout_change()
        self.status_var.set("RM Manifest built from group_config")

    def update_manifest(self):
        selected_key = self.selected_asset.resource_key if self.selected_asset is not None else ""
        manifest, report = self.service.update_manifest_from_graphics()
        ResourceManager.save_manifest(self.assets_dir, manifest)
        self.rm_manifest_loaded = True
        self.reload_index()
        if selected_key:
            self.reselect_asset(selected_key)
        self.show_output(report.to_text())
        self.refresh_preview_after_layout_change()
        self.status_var.set("RM Manifest updated from group_config")

    def create_or_update_rm_manifest(self):
        manifest_path = ResourceManager.get_manifest_path(self.assets_dir)
        if os.path.exists(manifest_path):
            self.update_manifest()
        else:
            self.build_manifest()

    def show_output(self, text):
        self.hide_details_output()
        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert("1.0", text)
        self.output_text.configure(state="disabled")
        self.refresh_preview_after_layout_change()

    def hide_details_output(self):
        if hasattr(self, "output_text"):
            self.output_text.grid_remove()

    def copy_to_clipboard(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()


def find_project_assets_dir():
    return os.path.join(PROJECT_DIR, "assets")


def main():
    assets_dir = sys.argv[1] if len(sys.argv) > 1 else find_project_assets_dir()
    root = tk.Tk()
    ResourcePickerApp(root, assets_dir)
    root.mainloop()


if __name__ == "__main__":
    main()
