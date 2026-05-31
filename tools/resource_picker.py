"""Dev-утилита просмотра runtime-кэша ResourceManager."""

import json
import os
import sys
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from core.resource import ResourceManager  # noqa: E402


class ResourcePickerApp:
    """Tkinter-просмотрщик runtime-кэша ресурсов проекта."""

    WINDOW_SIZE = "800x600"
    PREVIEW_SIZE = (430, 390)

    def __init__(self, root, assets_dir):
        self.root = root
        self.assets_dir = os.path.abspath(assets_dir)
        self.runtime_cache = ResourceManager.build_index(self.assets_dir)
        self.records = list(self.runtime_cache.values())
        self.visible_records = self.records[:]
        self.records_by_item = {}
        self.folder_items = {}
        self.preview_image = None
        self.selected_record = None

        self.configure_window()
        self.create_widgets()
        self.populate_tree(self.visible_records)

    def configure_window(self):
        """Настроить окно и темную тему ttk."""
        self.root.title("Resource Picker")
        self.root.geometry(self.WINDOW_SIZE)
        self.root.minsize(800, 600)
        self.root.configure(bg="#1e1f22")

        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", background="#1e1f22", foreground="#e6e6e6", fieldbackground="#2b2d31")
        style.configure(
            "Treeview",
            background="#25272d",
            foreground="#e6e6e6",
            fieldbackground="#25272d",
        )
        style.configure("Treeview.Heading", background="#30333a", foreground="#ffffff")
        style.map("Treeview", background=[("selected", "#3f5f8f")])

    def create_widgets(self):
        """Создать поиск, навигатор, details, preview и Apply."""
        self.root.columnconfigure(0, weight=0)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        left_frame = ttk.Frame(self.root, padding=8)
        left_frame.grid(row=0, column=0, sticky="ns")
        left_frame.rowconfigure(2, weight=1)

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.on_search)
        search_frame = ttk.Frame(left_frame)
        search_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        search_frame.columnconfigure(1, weight=1)

        ttk.Label(search_frame, text="Search").grid(row=0, column=0, sticky="w", padx=(0, 6))
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=34)
        search_entry.grid(row=0, column=1, sticky="ew")
        ttk.Button(search_frame, text="Clear", command=self.clear_search).grid(row=0, column=2, sticky="e", padx=(6, 0))

        self.result_var = tk.StringVar()
        self.result_label = ttk.Label(left_frame, textvariable=self.result_var)
        self.result_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 6))

        self.tree = ttk.Treeview(
            left_frame,
            columns=("type", "size"),
            show="tree headings",
            height=16,
        )
        self.tree.heading("#0", text="Assets")
        self.tree.heading("type", text="Type")
        self.tree.heading("size", text="Size")
        self.tree.column("#0", width=320)
        self.tree.column("type", width=80, anchor="center")
        self.tree.column("size", width=80, anchor="center")
        self.tree.grid(row=2, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        tree_scroll = ttk.Scrollbar(left_frame, orient="vertical", command=self.tree.yview)
        tree_scroll.grid(row=2, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=tree_scroll.set)

        self.details = tk.Text(
            left_frame,
            width=50,
            height=12,
            bg="#1b1c20",
            fg="#e6e6e6",
            insertbackground="#e6e6e6",
            relief="flat",
            wrap="word",
        )
        self.details.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.details.configure(state="disabled")

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

        self.apply_button = ttk.Button(right_frame, text="Apply", command=self.apply_selection)
        self.apply_button.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        self.payload_text = tk.Text(
            right_frame,
            height=7,
            bg="#1b1c20",
            fg="#e6e6e6",
            insertbackground="#e6e6e6",
            relief="flat",
            wrap="none",
        )
        self.payload_text.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self.payload_text.configure(state="disabled")

    def populate_tree(self, records):
        """Заполнить дерево папками assets/ и ресурсами текущей выборки."""
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
                values=(record.resource_type, f"{record.scaled_size[0]}x{record.scaled_size[1]}"),
            )
            self.records_by_item[item_id] = record

        if query_is_active:
            self.expand_all_tree_items()

        self.update_result_label()

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
                    values=("folder", ""),
                    open=False,
                )
            parent_id = self.folder_items[folder_key]

        return parent_id

    def expand_all_tree_items(self):
        """Раскрыть все папки после поиска, чтобы найденные ресурсы были видны."""
        for item_id in self.folder_items.values():
            self.tree.item(item_id, open=True)

    def on_search(self, *_args):
        """Отфильтровать runtime-кэш по текстовому запросу."""
        query = self.search_var.get().strip().lower()
        if not query:
            self.visible_records = self.records[:]
        else:
            self.visible_records = [
                record
                for record in self.records
                if self.matches_query(record, query)
            ]
        self.clear_selection()
        self.populate_tree(self.visible_records)

    def clear_search(self):
        """Очистить поисковый запрос и вернуть полное дерево assets/."""
        self.search_var.set("")

    def update_result_label(self):
        """Показать количество найденных ресурсов."""
        total_count = len(self.records)
        visible_count = len(self.visible_records)
        query = self.search_var.get().strip()
        if query:
            self.result_var.set(f"Found: {visible_count} / {total_count}")
        else:
            self.result_var.set(f"Resources: {total_count}")

    @staticmethod
    def matches_query(record, query):
        """Проверить совпадение record с поисковым запросом."""
        tokens = query.split()
        haystack = " ".join(
            [
                record.key,
                record.file_name,
                record.relative_path,
                record.resource_type,
            ]
        ).lower()
        return all(token in haystack for token in tokens)

    def on_select(self, _event):
        """Обновить details и preview для выбранного ресурса."""
        selection = self.tree.selection()
        if not selection:
            return
        if selection[0] not in self.records_by_item:
            self.clear_selection()
            return

        self.selected_record = self.records_by_item[selection[0]]
        self.show_details(self.selected_record)
        self.show_preview(self.selected_record)

    def clear_selection(self):
        """Сбросить выбранный ресурс, details, preview и payload."""
        self.selected_record = None
        self.preview_image = None
        self.preview_label.configure(image="", text="Выберите ресурс слева")

        self.details.configure(state="normal")
        self.details.delete("1.0", tk.END)
        self.details.configure(state="disabled")

        self.payload_text.configure(state="normal")
        self.payload_text.delete("1.0", tk.END)
        self.payload_text.configure(state="disabled")

    def show_details(self, record):
        """Показать параметры ресурса из runtime-кэша."""
        payload = record.to_payload()
        lines = [
            f"resource_key: {payload['resource_key']}",
            f"resource_type: {payload['resource_type']}",
            f"file_name: {payload['file_name']}",
            f"relative_path: {payload['relative_path']}",
            f"path: {payload['path']}",
            f"original_size: {payload['original_size']}",
            f"scaled_size: {payload['scaled_size']}",
        ]

        if payload["target_height"] is not None:
            lines.append(f"target_height: {payload['target_height']}")
        if payload["rows"] is not None:
            lines.append(f"rows: {payload['rows']}")
            lines.append(f"columns: {payload['columns']}")
            lines.append(f"target_frame_height: {payload['target_frame_height']}")

        self.details.configure(state="normal")
        self.details.delete("1.0", tk.END)
        self.details.insert("1.0", "\n".join(lines))
        self.details.configure(state="disabled")

    def show_preview(self, record):
        """Показать изображение в правой панели."""
        with Image.open(record.path) as image:
            image = image.convert("RGBA")
            image.thumbnail(self.PREVIEW_SIZE)
            self.preview_image = ImageTk.PhotoImage(image)

        self.preview_label.configure(image=self.preview_image, text="")

    def apply_selection(self):
        """Сформировать payload выбранного ресурса для GuiActorFactory."""
        if self.selected_record is None:
            return

        payload = self.create_factory_payload(self.selected_record)
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        print(text)

        self.payload_text.configure(state="normal")
        self.payload_text.delete("1.0", tk.END)
        self.payload_text.insert("1.0", text)
        self.payload_text.configure(state="disabled")

    @staticmethod
    def create_factory_payload(record):
        """Создать payload, пригодный для GuiActorFactory.

        Payload не создает actor сам. Он подсказывает, какие поля можно
        вставить в будущую конфигурацию: local resource name, resource key и
        слой, который ссылается на этот local name.
        """
        local_name = ResourcePickerApp.create_local_resource_name(record)
        payload = record.to_payload()
        payload["factory"] = {
            "local_resource_name": local_name,
            "resource_key": record.key,
            "resource_kind": record.resource_type,
            "layer": {
                "name": local_name,
                "type": "animation" if record.resource_type == "animation" else "static",
                "resource": local_name,
                "offset": [0, 0],
                "visible": True,
                "alpha": 255,
            },
        }

        if record.resource_type == "animation":
            payload["factory"]["animation_resources"] = {local_name: record.key}
            payload["factory"]["static_resources"] = {}
        else:
            payload["factory"]["static_resources"] = {local_name: record.key}
            payload["factory"]["animation_resources"] = {}
        return payload

    @staticmethod
    def create_local_resource_name(record):
        """Создать короткое local name для ресурса внутри GuiActor."""
        name, _ext = os.path.splitext(record.file_name)
        return name.strip().replace(" ", "_")


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
