"""Dev utility for PNG resources, PNG frame metadata, and derived manifests."""

from __future__ import annotations

from dataclasses import dataclass, field
import importlib
import os
import re
import sys
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageDraw, ImageTk
from PIL.PngImagePlugin import PngInfo

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from core.resource import ResourceManager  # noqa: E402


FRAME_WIDTH_KEY = "frame_width"
FRAME_HEIGHT_KEY = "frame_height"


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
    asset: PngAsset | None
    status: str
    warnings: tuple[str, ...] = ()

    @property
    def display_name(self):
        return f"({self.local_name!r}, {self.resource_key!r})"


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
        package_dir = os.path.join(self.project_dir, "groups_store")
        if not os.path.isdir(package_dir):
            return entries

        for file_name in sorted(os.listdir(package_dir)):
            if not file_name.endswith(".py") or file_name == "__init__.py":
                continue

            module_name = f"groups_store.{os.path.splitext(file_name)[0]}"
            module = importlib.import_module(module_name)
            for local_name, resource_key in self.iter_graphics(getattr(module, "GRAPHICS", ())):
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
                        group_module=module_name,
                        group_file=file_name,
                        local_name=local_name,
                        resource_key=resource_key,
                        asset=asset,
                        status=status,
                        warnings=tuple(warnings),
                    )
                )
        return entries

    @staticmethod
    def iter_graphics(graphics):
        for item in graphics:
            if isinstance(item, dict):
                local_name = item.get("name") or item.get("layer_name") or item.get("local_name")
                resource_key = item.get("resource_key")
            elif isinstance(item, (tuple, list)) and len(item) >= 2:
                local_name, resource_key = item[0], item[1]
            else:
                continue

            if local_name and resource_key:
                yield str(local_name), str(resource_key)

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
        report = OperationReport("Build Manifest")
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

        update_report = OperationReport("Manifest Update")
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

    def load_manifest_if_exists(self):
        manifest_path = ResourceManager.get_manifest_path(self.assets_dir)
        if not os.path.exists(manifest_path):
            return {"resources": {}}
        return ResourceManager.load_manifest(self.assets_dir)

    @staticmethod
    def create_graphics_snippet(asset):
        local_name = ResourcePickerService.create_local_name_from_file(asset.file_name)
        return f"({local_name!r}, {asset.resource_key!r}),"

    @staticmethod
    def create_local_name_from_file(file_name):
        name, _ext = os.path.splitext(file_name)
        return re.sub(r"\W+", "_", name.strip()).strip("_") or "resource"


class ResourcePickerApp:
    """Tkinter shell for resource picker workflows."""

    WINDOW_SIZE = "1040x700"
    PREVIEW_SIZE = (560, 380)

    def __init__(self, root, assets_dir):
        self.root = root
        self.assets_dir = os.path.abspath(assets_dir)
        self.service = ResourcePickerService(PROJECT_DIR, self.assets_dir)
        self.manifest = {"resources": {}}
        self.png_assets = []
        self.visible_png_assets = []
        self.graphics_entries = []
        self.visible_graphics_entries = []
        self.png_assets_by_item = {}
        self.graphics_by_item = {}
        self.png_folder_items = {}
        self.group_items = {}
        self.preview_image = None
        self.selected_asset = None
        self.selected_graphic = None

        self.resource_key_var = tk.StringVar()
        self.path_var = tk.StringVar()
        self.png_size_var = tk.StringVar()
        self.frame_width_var = tk.StringVar()
        self.frame_height_var = tk.StringVar()
        self.details_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self.search_var = tk.StringVar()
        self.result_var = tk.StringVar()

        self.configure_window()
        self.create_widgets()
        self.search_var.trace_add("write", self.on_search)
        self.reload_index()

    def configure_window(self):
        self.root.title("Resource Picker")
        self.root.geometry(self.WINDOW_SIZE)
        self.root.minsize(980, 640)
        self.root.configure(bg="#1e1f22")

        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", background="#1e1f22", foreground="#e6e6e6", fieldbackground="#2b2d31")
        style.configure("Treeview", background="#25272d", foreground="#e6e6e6", fieldbackground="#25272d")
        style.configure("Treeview.Heading", background="#30333a", foreground="#ffffff")
        style.configure("TLabelframe", background="#1e1f22", foreground="#e6e6e6")
        style.map("Treeview", background=[("selected", "#3f5f8f")])

    def create_widgets(self):
        self.root.columnconfigure(0, weight=0)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        left_panel = ttk.Frame(self.root, padding=8)
        left_panel.grid(row=0, column=0, sticky="ns")
        left_panel.rowconfigure(3, weight=1)

        self.create_toolbar(left_panel)
        self.create_search(left_panel)
        self.create_resource_tabs(left_panel)
        self.create_metadata_editor(left_panel)
        self.create_preview_panel()

    def create_toolbar(self, parent):
        toolbar = ttk.Frame(parent)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        toolbar.columnconfigure(0, weight=1)
        toolbar.columnconfigure(1, weight=1)

        ttk.Button(toolbar, text="Build Manifest", command=self.build_manifest).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        ttk.Button(toolbar, text="Manifest Update", command=self.update_manifest).grid(
            row=0, column=1, sticky="ew", padx=(4, 0)
        )

    def create_search(self, parent):
        search_frame = ttk.Frame(parent)
        search_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        search_frame.columnconfigure(1, weight=1)

        ttk.Label(search_frame, text="Search PNG").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Entry(search_frame, textvariable=self.search_var, width=34).grid(row=0, column=1, sticky="ew")
        ttk.Button(search_frame, text="Clear", command=self.clear_search).grid(row=0, column=2, sticky="e", padx=(6, 0))
        ttk.Label(parent, textvariable=self.result_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 6))

    def create_resource_tabs(self, parent):
        self.tabs = ttk.Notebook(parent)
        self.tabs.grid(row=3, column=0, columnspan=2, sticky="nsew")
        self.tabs.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        png_tab = ttk.Frame(self.tabs)
        manifest_tab = ttk.Frame(self.tabs)
        png_tab.rowconfigure(0, weight=1)
        png_tab.columnconfigure(0, weight=1)
        manifest_tab.rowconfigure(0, weight=1)
        manifest_tab.columnconfigure(0, weight=1)

        self.tabs.add(png_tab, text="PNG Explorer")
        self.tabs.add(manifest_tab, text="Manifest Explorer")

        self.create_png_tree(png_tab)
        self.create_manifest_tree(manifest_tab)

    def create_png_tree(self, parent):
        self.png_tree = ttk.Treeview(parent, columns=("key", "frame", "size"), show="tree headings", height=16)
        self.png_tree.heading("#0", text="PNG")
        self.png_tree.heading("key", text="Resource key")
        self.png_tree.heading("frame", text="Frame")
        self.png_tree.heading("size", text="PNG")
        self.png_tree.column("#0", width=230)
        self.png_tree.column("key", width=250)
        self.png_tree.column("frame", width=90, anchor="center")
        self.png_tree.column("size", width=90, anchor="center")
        self.png_tree.grid(row=0, column=0, sticky="nsew")
        self.png_tree.bind("<<TreeviewSelect>>", self.on_png_select)

        tree_scroll = ttk.Scrollbar(parent, orient="vertical", command=self.png_tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.png_tree.configure(yscrollcommand=tree_scroll.set)

        ttk.Button(parent, text="Get PNG resource", command=self.get_png_resource).grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )

    def create_manifest_tree(self, parent):
        self.manifest_tree = ttk.Treeview(parent, columns=("key", "status"), show="tree headings", height=16)
        self.manifest_tree.heading("#0", text="Group / PNG resource")
        self.manifest_tree.heading("key", text="Resource key")
        self.manifest_tree.heading("status", text="Status")
        self.manifest_tree.column("#0", width=280)
        self.manifest_tree.column("key", width=250)
        self.manifest_tree.column("status", width=120, anchor="center")
        self.manifest_tree.grid(row=0, column=0, sticky="nsew")
        self.manifest_tree.bind("<<TreeviewSelect>>", self.on_manifest_select)

        tree_scroll = ttk.Scrollbar(parent, orient="vertical", command=self.manifest_tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.manifest_tree.configure(yscrollcommand=tree_scroll.set)

    def create_metadata_editor(self, parent):
        form = ttk.LabelFrame(parent, text="PNG Metadata Editor", padding=8)
        form.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="resource_key").grid(row=0, column=0, sticky="w", pady=(0, 4))
        ttk.Label(form, textvariable=self.resource_key_var).grid(row=0, column=1, sticky="w", pady=(0, 4))

        ttk.Label(form, text="path").grid(row=1, column=0, sticky="w", pady=(0, 4))
        ttk.Label(form, textvariable=self.path_var).grid(row=1, column=1, sticky="w", pady=(0, 4))

        ttk.Label(form, text="png_size").grid(row=2, column=0, sticky="w", pady=(0, 4))
        ttk.Label(form, textvariable=self.png_size_var).grid(row=2, column=1, sticky="w", pady=(0, 4))

        ttk.Label(form, text="frame_width").grid(row=3, column=0, sticky="w", pady=(0, 4))
        ttk.Entry(form, textvariable=self.frame_width_var).grid(row=3, column=1, sticky="ew", pady=(0, 4))

        ttk.Label(form, text="frame_height").grid(row=4, column=0, sticky="w", pady=(0, 4))
        ttk.Entry(form, textvariable=self.frame_height_var).grid(row=4, column=1, sticky="ew", pady=(0, 4))

        ttk.Label(form, textvariable=self.details_var, wraplength=430).grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(4, 8)
        )
        ttk.Button(form, text="Save PNG metadata", command=self.save_png_metadata).grid(
            row=6, column=0, columnspan=2, sticky="ew"
        )

    def create_preview_panel(self):
        right_panel = ttk.Frame(self.root, padding=8)
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(0, weight=1)

        self.preview_label = tk.Label(
            right_panel,
            bg="#111214",
            fg="#e6e6e6",
            text="Select a PNG resource",
            compound="center",
        )
        self.preview_label.grid(row=0, column=0, sticky="nsew")

        ttk.Label(right_panel, textvariable=self.status_var).grid(row=1, column=0, sticky="w", pady=(8, 0))

        self.output_text = tk.Text(
            right_panel,
            height=14,
            bg="#1b1c20",
            fg="#e6e6e6",
            insertbackground="#e6e6e6",
            relief="flat",
            wrap="none",
        )
        self.output_text.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self.output_text.configure(state="disabled")

    def reload_index(self):
        self.manifest = self.service.load_manifest_if_exists()
        self.png_assets = self.service.load_png_assets()
        assets_by_key = {asset.resource_key: asset for asset in self.png_assets}
        self.graphics_entries = self.service.load_graphics_entries(assets_by_key=assets_by_key, manifest=self.manifest)
        self.visible_png_assets = self.filter_png_assets()
        self.visible_graphics_entries = self.filter_graphics_entries()
        self.populate_png_tree(self.visible_png_assets)
        self.populate_manifest_tree(self.visible_graphics_entries)
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
                values=(asset.resource_key, frame_size, f"{asset.size[0]}x{asset.size[1]}"),
            )
            self.png_assets_by_item[item_id] = asset

        if query_is_active:
            for item_id in self.png_folder_items.values():
                self.png_tree.item(item_id, open=True)

    @staticmethod
    def format_frame_size(asset):
        frame_width, frame_height = asset.manifest_frame_size
        suffix = " !" if asset.metadata.warnings else ""
        return f"{frame_width}x{frame_height}{suffix}"

    def populate_manifest_tree(self, entries):
        self.manifest_tree.delete(*self.manifest_tree.get_children())
        self.graphics_by_item = {}
        self.group_items = {}
        query_is_active = bool(self.search_var.get().strip())

        for entry in sorted(entries, key=lambda item: (item.group_file.lower(), item.local_name.lower())):
            group_item = self.group_items.get(entry.group_file)
            if group_item is None:
                group_item = self.manifest_tree.insert(
                    "",
                    "end",
                    text=entry.group_file,
                    values=("", ""),
                    open=query_is_active,
                )
                self.group_items[entry.group_file] = group_item
            item_id = self.manifest_tree.insert(
                group_item,
                "end",
                text=entry.display_name,
                values=(entry.resource_key, entry.status),
            )
            self.graphics_by_item[item_id] = entry

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
                    values=("", "folder", ""),
                    open=False,
                )
            parent_id = self.png_folder_items[folder_key]
        return parent_id

    def on_search(self, *_args):
        self.visible_png_assets = self.filter_png_assets()
        self.visible_graphics_entries = self.filter_graphics_entries()
        self.clear_selection(clear_output=False)
        self.populate_png_tree(self.visible_png_assets)
        self.populate_manifest_tree(self.visible_graphics_entries)
        self.update_result_label()

    def on_tab_changed(self, _event):
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
        tab_name = self.tabs.tab(self.tabs.select(), "text") if hasattr(self, "tabs") else "PNG Explorer"
        query = self.search_var.get().strip()
        if tab_name == "Manifest Explorer":
            total = len(self.graphics_entries)
            visible = len(self.visible_graphics_entries)
            noun = "manifest resources"
        else:
            total = len(self.png_assets)
            visible = len(self.visible_png_assets)
            noun = "PNG resources"
        self.result_var.set(f"Found: {visible} / {total} {noun}" if query else f"{total} {noun}")

    def on_png_select(self, _event):
        selection = self.png_tree.selection()
        if not selection:
            return
        item_id = selection[0]
        if item_id not in self.png_assets_by_item:
            self.clear_selection(clear_output=False)
            return
        self.selected_asset = self.png_assets_by_item[item_id]
        self.selected_graphic = None
        self.show_asset(self.selected_asset)

    def on_manifest_select(self, _event):
        selection = self.manifest_tree.selection()
        if not selection:
            return
        item_id = selection[0]
        if item_id not in self.graphics_by_item:
            self.clear_selection(clear_output=False)
            return
        self.selected_graphic = self.graphics_by_item[item_id]
        self.selected_asset = self.selected_graphic.asset
        if self.selected_asset is None:
            self.clear_metadata_fields()
            self.status_var.set(self.selected_graphic.status)
            self.show_output("\n".join(self.selected_graphic.warnings))
            return
        self.show_asset(self.selected_asset, self.selected_graphic)

    def clear_selection(self, clear_output=True):
        self.selected_asset = None
        self.selected_graphic = None
        self.preview_image = None
        self.preview_label.configure(image="", text="Select a PNG resource")
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
        self.show_preview(asset)
        if graphic and graphic.warnings:
            self.show_output("\n".join(graphic.warnings))

    def show_preview(self, asset):
        with Image.open(asset.path) as image:
            image = image.convert("RGBA")
            self.draw_frame_grid(image, asset)
            image.thumbnail(self.PREVIEW_SIZE)
            self.preview_image = ImageTk.PhotoImage(image)
        self.preview_label.configure(image=self.preview_image, text="")

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
        self.status_var.set("PNG resource tuple copied")

    def save_png_metadata(self):
        if self.selected_asset is None:
            self.status_var.set("Select a PNG first")
            return
        try:
            frame_width = int(self.frame_width_var.get().strip())
            frame_height = int(self.frame_height_var.get().strip())
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

    def reselect_asset(self, resource_key):
        for item_id, asset in self.png_assets_by_item.items():
            if asset.resource_key == resource_key:
                self.png_tree.selection_set(item_id)
                self.png_tree.see(item_id)
                self.selected_asset = asset
                self.show_asset(asset)
                return

    def build_manifest(self):
        manifest, report = self.service.build_manifest_from_graphics()
        ResourceManager.save_manifest(self.assets_dir, manifest)
        self.reload_index()
        self.show_output(report.to_text())
        self.status_var.set("Manifest built from groups_store GRAPHICS")

    def update_manifest(self):
        manifest, report = self.service.update_manifest_from_graphics()
        ResourceManager.save_manifest(self.assets_dir, manifest)
        self.reload_index()
        self.show_output(report.to_text())
        self.status_var.set("Manifest updated from groups_store GRAPHICS")

    def show_output(self, text):
        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert("1.0", text)
        self.output_text.configure(state="disabled")

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
