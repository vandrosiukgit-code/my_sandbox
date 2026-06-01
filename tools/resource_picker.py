"""Dev-утилита просмотра assets/ и редактирования resource_manifest.json."""

import importlib
import os
import re
import sys
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from core.resource import ResourceManager  # noqa: E402


class ResourcePickerApp:
    """Tkinter-инструмент для работы с manifest ресурсов."""

    WINDOW_SIZE = "900x640"
    PREVIEW_SIZE = (460, 330)

    def __init__(self, root, assets_dir):
        self.root = root
        self.assets_dir = os.path.abspath(assets_dir)
        self.manifest = {"resources": {}}
        self.records = []
        self.visible_records = []
        self.records_by_item = {}
        self.folder_items = {}
        self.raw_assets = []
        self.visible_raw_assets = []
        self.raw_assets_by_item = {}
        self.raw_folder_items = {}
        self.preview_image = None
        self.selected_record = None
        self.selected_raw_asset = None

        self.resource_key_var = tk.StringVar()
        self.path_var = tk.StringVar()
        self.frame_width_var = tk.StringVar()
        self.frame_height_var = tk.StringVar()

        self.configure_window()
        self.create_widgets()
        self.reload_index()

    def configure_window(self):
        """Настроить окно и темную тему ttk."""
        self.root.title("Resource Picker")
        self.root.geometry(self.WINDOW_SIZE)
        self.root.minsize(900, 640)
        self.root.configure(bg="#1e1f22")

        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", background="#1e1f22", foreground="#e6e6e6", fieldbackground="#2b2d31")
        style.configure("Treeview", background="#25272d", foreground="#e6e6e6", fieldbackground="#25272d")
        style.configure("Treeview.Heading", background="#30333a", foreground="#ffffff")
        style.map("Treeview", background=[("selected", "#3f5f8f")])

    def create_widgets(self):
        """Создать поиск, дерево manifest, форму, preview и кнопки."""
        self.root.columnconfigure(0, weight=0)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        left_frame = ttk.Frame(self.root, padding=8)
        left_frame.grid(row=0, column=0, sticky="ns")
        left_frame.rowconfigure(3, weight=1)

        self.create_toolbar(left_frame)
        self.create_search(left_frame)
        self.create_resource_tabs(left_frame)
        self.create_manifest_form(left_frame)
        self.create_preview_panel()

    def create_toolbar(self, parent):
        """Создать кнопки управления manifest."""
        toolbar = ttk.Frame(parent)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        toolbar.columnconfigure(0, weight=1)
        toolbar.columnconfigure(1, weight=1)
        toolbar.columnconfigure(2, weight=1)

        ttk.Button(toolbar, text="Generate manifest", command=self.generate_manifest).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(toolbar, text="Save manifest", command=self.save_manifest).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(toolbar, text="Prune manifest", command=self.prune_manifest).grid(row=0, column=2, sticky="ew", padx=(4, 0))

    def create_search(self, parent):
        """Создать строку поиска по manifest."""
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.on_search)

        search_frame = ttk.Frame(parent)
        search_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        search_frame.columnconfigure(1, weight=1)

        ttk.Label(search_frame, text="Search").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Entry(search_frame, textvariable=self.search_var, width=34).grid(row=0, column=1, sticky="ew")
        ttk.Button(search_frame, text="Clear", command=self.clear_search).grid(row=0, column=2, sticky="e", padx=(6, 0))

        self.result_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.result_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 6))

    def create_resource_tabs(self, parent):
        """Создать вкладки manifest и сырых assets."""
        tabs = ttk.Notebook(parent)
        tabs.grid(row=3, column=0, columnspan=2, sticky="nsew")

        manifest_tab = ttk.Frame(tabs)
        raw_assets_tab = ttk.Frame(tabs)
        manifest_tab.rowconfigure(0, weight=1)
        manifest_tab.columnconfigure(0, weight=1)
        raw_assets_tab.rowconfigure(0, weight=1)
        raw_assets_tab.columnconfigure(0, weight=1)

        tabs.add(manifest_tab, text="Manifest")
        tabs.add(raw_assets_tab, text="Raw assets")

        self.create_manifest_tree(manifest_tab)
        self.create_raw_assets_tree(raw_assets_tab)

    def create_manifest_tree(self, parent):
        """Создать дерево manifest по путям assets/."""
        self.tree = ttk.Treeview(parent, columns=("key", "frame", "size"), show="tree headings", height=15)
        self.tree.heading("#0", text="Assets")
        self.tree.heading("key", text="Resource key")
        self.tree.heading("frame", text="Frame")
        self.tree.heading("size", text="PNG")
        self.tree.column("#0", width=240)
        self.tree.column("key", width=220)
        self.tree.column("frame", width=90, anchor="center")
        self.tree.column("size", width=90, anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        tree_scroll = ttk.Scrollbar(parent, orient="vertical", command=self.tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=tree_scroll.set)

    def create_raw_assets_tree(self, parent):
        """Создать дерево всех PNG из assets/ независимо от manifest."""
        self.raw_tree = ttk.Treeview(parent, columns=("key", "size"), show="tree headings", height=15)
        self.raw_tree.heading("#0", text="Raw PNG")
        self.raw_tree.heading("key", text="Default resource key")
        self.raw_tree.heading("size", text="PNG")
        self.raw_tree.column("#0", width=240)
        self.raw_tree.column("key", width=260)
        self.raw_tree.column("size", width=90, anchor="center")
        self.raw_tree.grid(row=0, column=0, sticky="nsew")
        self.raw_tree.bind("<<TreeviewSelect>>", self.on_raw_asset_select)

        tree_scroll = ttk.Scrollbar(parent, orient="vertical", command=self.raw_tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.raw_tree.configure(yscrollcommand=tree_scroll.set)

        copy_button = ttk.Button(parent, text="Copy GRAPHICS snippet", command=self.copy_raw_asset_snippet)
        copy_button.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

    def create_manifest_form(self, parent):
        """Создать форму редактирования записи manifest."""
        form = ttk.LabelFrame(parent, text="Manifest record", padding=8)
        form.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="resource_key").grid(row=0, column=0, sticky="w", pady=(0, 4))
        ttk.Entry(form, textvariable=self.resource_key_var).grid(row=0, column=1, sticky="ew", pady=(0, 4))

        ttk.Label(form, text="path").grid(row=1, column=0, sticky="w", pady=(0, 4))
        ttk.Entry(form, textvariable=self.path_var).grid(row=1, column=1, sticky="ew", pady=(0, 4))

        ttk.Label(form, text="frame_width").grid(row=2, column=0, sticky="w", pady=(0, 4))
        ttk.Entry(form, textvariable=self.frame_width_var).grid(row=2, column=1, sticky="ew", pady=(0, 4))

        ttk.Label(form, text="frame_height").grid(row=3, column=0, sticky="w", pady=(0, 4))
        ttk.Entry(form, textvariable=self.frame_height_var).grid(row=3, column=1, sticky="ew", pady=(0, 4))

        self.details_var = tk.StringVar()
        ttk.Label(form, textvariable=self.details_var).grid(row=4, column=0, columnspan=2, sticky="w", pady=(4, 8))

        buttons = ttk.Frame(form)
        buttons.grid(row=5, column=0, columnspan=2, sticky="ew")
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)
        ttk.Button(buttons, text="Save record", command=self.save_record).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(buttons, text="Save + Copy GRAPHICS", command=self.apply_selection).grid(row=0, column=1, sticky="ew", padx=(4, 0))

    def create_preview_panel(self):
        """Создать правую панель preview и snippet."""
        right_frame = ttk.Frame(self.root, padding=8)
        right_frame.grid(row=0, column=1, sticky="nsew")
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(0, weight=1)

        self.preview_label = tk.Label(
            right_frame,
            bg="#111214",
            fg="#e6e6e6",
            text="Выберите ресурс слева",
            compound="center",
        )
        self.preview_label.grid(row=0, column=0, sticky="nsew")

        self.status_var = tk.StringVar()
        ttk.Label(right_frame, textvariable=self.status_var).grid(row=1, column=0, sticky="w", pady=(8, 0))

        self.payload_text = tk.Text(
            right_frame,
            height=12,
            bg="#1b1c20",
            fg="#e6e6e6",
            insertbackground="#e6e6e6",
            relief="flat",
            wrap="none",
        )
        self.payload_text.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self.payload_text.configure(state="disabled")

    def reload_index(self):
        """Перечитать manifest и пересобрать metadata-index."""
        self.manifest = ResourceManager.load_or_generate_manifest(self.assets_dir)
        ResourceManager.build_index(self.assets_dir)
        self.manifest = ResourceManager._manifest
        manifest_warnings = ResourceManager.get_manifest_warnings()
        self.records = list(ResourceManager.get_runtime_cache().values())
        self.visible_records = self.filter_records()
        self.raw_assets = self.load_raw_assets()
        self.visible_raw_assets = self.filter_raw_assets()
        self.populate_tree(self.visible_records)
        self.populate_raw_assets_tree(self.visible_raw_assets)
        if manifest_warnings:
            warning_text = "\n\n".join(manifest_warnings)
            self.status_var.set("Manifest repaired from PNG sizes; update PNG metadata")
            messagebox.showwarning("PNG metadata review needed", warning_text)

    def generate_manifest(self):
        """Сгенерировать manifest из всех PNG и сохранить его на диск."""
        self.manifest = ResourceManager.generate_manifest(self.assets_dir)
        ResourceManager.save_manifest(self.assets_dir, self.manifest)
        self.reload_index()
        self.status_var.set("Manifest generated from assets/")

    def save_manifest(self):
        """Сохранить текущий manifest на диск."""
        ResourceManager.save_manifest(self.assets_dir, self.manifest)
        self.reload_index()
        self.status_var.set("Manifest saved")

    def prune_manifest(self):
        """Удалить из manifest ресурсы, которые не используются в GRAPHICS."""
        used_keys = self.collect_used_resource_keys()
        resources = self.manifest.get("resources", {})
        before_keys = set(resources)
        missing_keys = sorted(used_keys - before_keys)
        removed_keys = sorted(before_keys - used_keys)

        self.manifest["resources"] = {
            key: resources[key]
            for key in sorted(before_keys & used_keys)
        }
        ResourceManager.save_manifest(self.assets_dir, self.manifest)
        self.reload_index()

        report = [
            f"Used resources: {len(used_keys)}",
            f"Removed unused: {len(removed_keys)}",
            f"Missing in manifest: {len(missing_keys)}",
        ]
        if removed_keys:
            report.append("")
            report.append("Removed:")
            report.extend(removed_keys)
        if missing_keys:
            report.append("")
            report.append("Missing:")
            report.extend(missing_keys)
        self.show_payload("\n".join(report))
        self.status_var.set("Manifest pruned by gui_actors_store GRAPHICS")

    def populate_tree(self, records):
        """Заполнить дерево папками assets/ и manifest-записями."""
        self.tree.delete(*self.tree.get_children())
        self.records_by_item = {}
        self.folder_items = {}

        query_is_active = bool(self.search_var.get().strip())
        for record in sorted(records, key=lambda item: item.relative_path.lower()):
            parent_id = self.ensure_folder_path(record.relative_path)
            item_id = self.tree.insert(
                parent_id,
                "end",
                text=record.file_name,
                values=(
                    record.key,
                    f"{record.frame_width}x{record.frame_height}",
                    f"{record.original_size[0]}x{record.original_size[1]}",
                ),
            )
            self.records_by_item[item_id] = record

        if query_is_active:
            self.expand_all_tree_items()

        self.update_result_label()

    def populate_raw_assets_tree(self, raw_assets):
        """Заполнить дерево сырых PNG из assets/."""
        self.raw_tree.delete(*self.raw_tree.get_children())
        self.raw_assets_by_item = {}
        self.raw_folder_items = {}

        query_is_active = bool(self.search_var.get().strip())
        for asset in sorted(raw_assets, key=lambda item: item["relative_path"].lower()):
            parent_id = self.ensure_raw_folder_path(asset["relative_path"])
            item_id = self.raw_tree.insert(
                parent_id,
                "end",
                text=asset["file_name"],
                values=(asset["resource_key"], f"{asset['size'][0]}x{asset['size'][1]}"),
            )
            self.raw_assets_by_item[item_id] = asset

        if query_is_active:
            for item_id in self.raw_folder_items.values():
                self.raw_tree.item(item_id, open=True)

    def ensure_folder_path(self, relative_path):
        """Создать недостающие папки для relative_path и вернуть id родителя файла."""
        parent_id = ""
        folder_parts = os.path.dirname(relative_path).replace("\\", "/").split("/")
        current_path = []

        for folder_name in folder_parts:
            if not folder_name:
                continue

            current_path.append(folder_name)
            folder_key = "/".join(current_path)
            if folder_key not in self.folder_items:
                self.folder_items[folder_key] = self.tree.insert(
                    parent_id,
                    "end",
                    text=folder_name,
                    values=("", "folder", ""),
                    open=False,
                )
            parent_id = self.folder_items[folder_key]

        return parent_id

    def ensure_raw_folder_path(self, relative_path):
        """Создать недостающие папки в дереве сырых assets."""
        parent_id = ""
        folder_parts = os.path.dirname(relative_path).replace("\\", "/").split("/")
        current_path = []

        for folder_name in folder_parts:
            if not folder_name:
                continue

            current_path.append(folder_name)
            folder_key = "/".join(current_path)
            if folder_key not in self.raw_folder_items:
                self.raw_folder_items[folder_key] = self.raw_tree.insert(
                    parent_id,
                    "end",
                    text=folder_name,
                    values=("", ""),
                    open=False,
                )
            parent_id = self.raw_folder_items[folder_key]

        return parent_id

    def expand_all_tree_items(self):
        """Раскрыть все папки после поиска, чтобы найденные ресурсы были видны."""
        for item_id in self.folder_items.values():
            self.tree.item(item_id, open=True)

    def on_search(self, *_args):
        """Отфильтровать manifest по текстовому запросу."""
        self.visible_records = self.filter_records()
        self.visible_raw_assets = self.filter_raw_assets()
        self.clear_selection()
        self.populate_tree(self.visible_records)
        self.populate_raw_assets_tree(self.visible_raw_assets)

    def filter_records(self):
        """Вернуть записи, подходящие под поисковый запрос."""
        query = self.search_var.get().strip().lower()
        if not query:
            return self.records[:]
        return [record for record in self.records if self.matches_query(record, query)]

    def filter_raw_assets(self):
        """Вернуть сырые PNG, подходящие под поисковый запрос."""
        query = self.search_var.get().strip().lower()
        if not query:
            return self.raw_assets[:]
        tokens = query.split()
        return [
            asset
            for asset in self.raw_assets
            if all(
                token in " ".join(
                    [asset["resource_key"], asset["file_name"], asset["relative_path"]]
                ).lower()
                for token in tokens
            )
        ]

    def clear_search(self):
        """Очистить поисковый запрос и вернуть полное дерево manifest."""
        self.search_var.set("")

    def update_result_label(self):
        """Показать количество найденных ресурсов."""
        total_count = len(self.records)
        visible_count = len(self.visible_records)
        query = self.search_var.get().strip()
        if query:
            self.result_var.set(f"Found: {visible_count} / {total_count}")
        else:
            self.result_var.set(f"Manifest resources: {total_count}")

    @staticmethod
    def matches_query(record, query):
        """Проверить совпадение record с поисковым запросом."""
        tokens = query.split()
        haystack = " ".join([record.key, record.file_name, record.relative_path]).lower()
        return all(token in haystack for token in tokens)

    def on_select(self, _event):
        """Обновить форму manifest и preview для выбранного ресурса."""
        selection = self.tree.selection()
        if not selection:
            return
        if selection[0] not in self.records_by_item:
            self.clear_selection()
            return

        self.selected_record = self.records_by_item[selection[0]]
        self.show_record(self.selected_record)
        self.show_preview(self.selected_record)

    def clear_selection(self):
        """Сбросить выбранный ресурс, форму, preview и payload."""
        self.selected_record = None
        self.selected_raw_asset = None
        self.preview_image = None
        self.preview_label.configure(image="", text="Выберите ресурс слева")
        self.resource_key_var.set("")
        self.path_var.set("")
        self.frame_width_var.set("")
        self.frame_height_var.set("")
        self.details_var.set("")
        self.status_var.set("")
        self.show_payload("")

    def on_raw_asset_select(self, _event):
        """Показать preview сырого PNG и подготовить snippet для GRAPHICS."""
        selection = self.raw_tree.selection()
        if not selection:
            return
        if selection[0] not in self.raw_assets_by_item:
            self.clear_selection()
            return

        self.selected_raw_asset = self.raw_assets_by_item[selection[0]]
        self.selected_record = None
        self.show_raw_asset(self.selected_raw_asset)
        self.show_raw_preview(self.selected_raw_asset)

    def show_raw_asset(self, asset):
        """Показать сведения о сыром PNG без изменения manifest."""
        self.resource_key_var.set(asset["resource_key"])
        self.path_var.set(asset["relative_path"])
        self.frame_width_var.set(str(asset["size"][0]))
        self.frame_height_var.set(str(asset["size"][1]))
        self.details_var.set(f"Raw PNG: {asset['size'][0]}x{asset['size'][1]}")
        self.show_payload(self.create_raw_graphic_snippet(asset))
        self.status_var.set("Raw asset selected")

    def show_raw_preview(self, asset):
        """Показать preview сырого PNG."""
        with Image.open(asset["path"]) as image:
            image = image.convert("RGBA")
            image.thumbnail(self.PREVIEW_SIZE)
            self.preview_image = ImageTk.PhotoImage(image)

        self.preview_label.configure(image=self.preview_image, text="")

    def show_record(self, record):
        """Показать manifest-запись выбранного ресурса в форме."""
        self.resource_key_var.set(record.key)
        self.path_var.set(record.relative_path)
        self.frame_width_var.set(str(record.frame_width))
        self.frame_height_var.set(str(record.frame_height))
        self.details_var.set(
            f"PNG: {record.original_size[0]}x{record.original_size[1]} | "
            f"rows: {record.rows}"
        )

    def show_preview(self, record):
        """Показать изображение в правой панели."""
        with Image.open(record.path) as image:
            image = image.convert("RGBA")
            image.thumbnail(self.PREVIEW_SIZE)
            self.preview_image = ImageTk.PhotoImage(image)

        self.preview_label.configure(image=self.preview_image, text="")

    def save_record(self):
        """Сохранить текущую форму в manifest."""
        if self.selected_record is None:
            return False

        old_key = self.selected_record.key
        new_key = self.resource_key_var.get().strip()
        if not new_key:
            messagebox.showerror("Manifest error", "resource_key не может быть пустым")
            return False

        try:
            entry = {
                "path": self.path_var.get().strip(),
                "frame_width": int(self.frame_width_var.get().strip()),
                "frame_height": int(self.frame_height_var.get().strip()),
            }
            ResourceManager.create_record(new_key, entry, self.assets_dir)
        except Exception as error:
            messagebox.showerror("Manifest error", str(error))
            return False

        resources = self.manifest.setdefault("resources", {})
        if old_key != new_key:
            resources.pop(old_key, None)
        resources[new_key] = entry
        self.manifest = ResourceManager.normalize_manifest(self.manifest)
        ResourceManager.save_manifest(self.assets_dir, self.manifest)

        selected_key = new_key
        self.reload_index()
        self.reselect_record_by_key(selected_key)
        self.status_var.set("Manifest record saved")
        return True

    def reselect_record_by_key(self, resource_key):
        """Вернуть выделение на ресурс после пересборки index."""
        for item_id, record in self.records_by_item.items():
            if record.key == resource_key:
                self.tree.selection_set(item_id)
                self.tree.see(item_id)
                self.selected_record = record
                self.show_record(record)
                self.show_preview(record)
                return

    def apply_selection(self):
        """Сохранить manifest-запись, сформировать snippet и скопировать его."""
        if self.selected_record is None:
            return
        if not self.save_record():
            return

        text = self.create_graphic_snippet(self.selected_record)
        print(text)
        self.show_payload(text)
        self.copy_to_clipboard(text)
        self.status_var.set("Manifest saved, snippet copied")

    def copy_raw_asset_snippet(self):
        """Скопировать snippet для GRAPHICS по выбранному сырому PNG."""
        if self.selected_raw_asset is None:
            return

        text = self.create_raw_graphic_snippet(self.selected_raw_asset)
        print(text)
        self.show_payload(text)
        self.copy_to_clipboard(text)
        self.status_var.set("GRAPHICS snippet copied from raw asset")

    @staticmethod
    def create_graphic_snippet(record):
        """Создать Python-snippet слоя для GRAPHICS в gui_actors_store/*."""
        local_name = ResourcePickerApp.create_local_resource_name(record)
        return f"({local_name!r}, {record.key!r}),"

    def show_payload(self, text):
        """Показать служебный текст в правой нижней панели."""
        self.payload_text.configure(state="normal")
        self.payload_text.delete("1.0", tk.END)
        self.payload_text.insert("1.0", text)
        self.payload_text.configure(state="disabled")

    def copy_to_clipboard(self, text):
        """Скопировать сгенерированный snippet в системный буфер обмена."""
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()

    @staticmethod
    def create_local_resource_name(record):
        """Создать короткое local name для ресурса внутри GuiActor."""
        name, _ext = os.path.splitext(record.file_name)
        return re.sub(r"\W+", "_", name.strip()).strip("_") or "resource"

    @classmethod
    def create_raw_graphic_snippet(cls, asset):
        """Создать Python-snippet слоя по сырому PNG."""
        local_name = cls.create_local_name_from_file(asset["file_name"])
        return f"({local_name!r}, {asset['resource_key']!r}),"

    @staticmethod
    def create_local_name_from_file(file_name):
        """Создать короткое local name по имени файла."""
        name, _ext = os.path.splitext(file_name)
        return re.sub(r"\W+", "_", name.strip()).strip("_") or "resource"

    def load_raw_assets(self):
        """Прочитать все PNG из assets/ как сырой склад графики."""
        assets = []
        for file_path in ResourceManager.get_png_files(self.assets_dir):
            relative_path = os.path.relpath(file_path, self.assets_dir).replace("\\", "/")
            with Image.open(file_path) as image:
                size = image.size
            assets.append(
                {
                    "path": os.path.abspath(file_path),
                    "relative_path": relative_path,
                    "file_name": os.path.basename(file_path),
                    "resource_key": ResourceManager.build_resource_key(relative_path),
                    "size": size,
                }
            )
        return assets

    @staticmethod
    def collect_used_resource_keys():
        """Собрать resource_key из GRAPHICS всех модулей gui_actors_store."""
        package_dir = os.path.join(PROJECT_DIR, "gui_actors_store")
        used_keys = set()
        for file_name in sorted(os.listdir(package_dir)):
            if not file_name.endswith(".py") or file_name == "__init__.py":
                continue

            module_name = f"gui_actors_store.{os.path.splitext(file_name)[0]}"
            module = importlib.import_module(module_name)
            graphics = getattr(module, "GRAPHICS", ())
            for item in graphics:
                resource_key = ResourcePickerApp.extract_resource_key(item)
                if resource_key:
                    used_keys.add(resource_key)
        return used_keys

    @staticmethod
    def extract_resource_key(graphic):
        """Достать resource_key из элемента GRAPHICS."""
        if isinstance(graphic, dict):
            return graphic.get("resource_key")
        if isinstance(graphic, (tuple, list)) and len(graphic) >= 2:
            return graphic[1]
        return None


def find_project_assets_dir():
    """Найти assets/ относительно расположения этого файла."""
    return os.path.join(PROJECT_DIR, "assets")


def main():
    """Запустить Resource Picker."""
    assets_dir = sys.argv[1] if len(sys.argv) > 1 else find_project_assets_dir()
    root = tk.Tk()
    ResourcePickerApp(root, assets_dir)
    root.mainloop()


if __name__ == "__main__":
    main()
