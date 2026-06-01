"""Загрузка PNG-ресурсов через manifest и сборка runtime-кэша кадров.

`assets/resource_manifest.json` является контрактом между сырыми PNG и
ResourceManager. В manifest хранится только описание того, как получить кадры
из файла: resource_key, путь к PNG и размер одного кадра.
"""

import json
import os
from dataclasses import dataclass

import pygame
from PIL import Image


@dataclass
class ResourceRecord:
    """Описание одного ресурса из manifest."""

    key: str
    path: str
    relative_path: str
    file_name: str
    original_size: tuple[int, int]
    frame_width: int
    frame_height: int
    rows: int
    columns: int = 1

    @property
    def frame_size(self):
        """Размер одного кадра ресурса."""
        return self.frame_width, self.frame_height

    def to_manifest_entry(self):
        """Вернуть запись, которую можно сохранить в resource_manifest.json."""
        return {
            "path": self.relative_path.replace("\\", "/"),
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
        }

    def to_payload(self):
        """Вернуть словарь для dev tools и отладки."""
        return {
            "resource_key": self.key,
            "path": self.path,
            "relative_path": self.relative_path,
            "file_name": self.file_name,
            "original_size": self.original_size,
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
            "rows": self.rows,
            "columns": self.columns,
        }


class ResourceManager:
    """Общий низкоуровневый склад графических ресурсов проекта."""

    MANIFEST_FILE_NAME = "resource_manifest.json"

    _cache_frames = {}
    _runtime_cache = {}
    _assets_dir = None
    _manifest = {"resources": {}}

    @classmethod
    def build_cache(cls, assets_dir, load_surfaces=True):
        """Построить runtime-index по manifest и при необходимости загрузить кадры."""
        cls.clear_cache()
        cls._assets_dir = os.path.abspath(assets_dir)
        cls._manifest = cls.load_or_generate_manifest(cls._assets_dir)

        for resource_key, entry in cls._manifest.get("resources", {}).items():
            record = cls.create_record(resource_key, entry, cls._assets_dir)
            cls._runtime_cache[record.key] = record

            if load_surfaces:
                cls.add_to_cache_frames_file(record.path, record.key)

        return cls._runtime_cache

    @classmethod
    def build_index(cls, assets_dir):
        """Построить metadata-only index без загрузки pygame.Surface."""
        return cls.build_cache(assets_dir, load_surfaces=False)

    @classmethod
    def build_runtime_cache(cls, assets_dir):
        """Построить runtime-index и загрузить кадры после создания display."""
        return cls.build_cache(assets_dir, load_surfaces=True)

    @classmethod
    def load_surfaces_from_index(cls):
        """Догрузить pygame.Surface для уже построенного runtime-index."""
        for record in cls._runtime_cache.values():
            cls.add_to_cache_frames_file(record.path, record.key)
        return cls._cache_frames

    @classmethod
    def clear_cache(cls):
        """Очистить runtime-index и загруженные кадры."""
        cls._cache_frames = {}
        cls._runtime_cache = {}
        cls._assets_dir = None
        cls._manifest = {"resources": {}}

    @classmethod
    def get_runtime_cache(cls):
        """Вернуть runtime-index key -> ResourceRecord."""
        return cls._runtime_cache

    @classmethod
    def get_runtime_payloads(cls):
        """Вернуть runtime-index в виде простых словарей."""
        return {key: record.to_payload() for key, record in cls._runtime_cache.items()}

    @classmethod
    def get_record(cls, key_or_path):
        """Получить ResourceRecord по resource_key или пути файла."""
        key = cls.resolve_resource_key(key_or_path)
        try:
            return cls._runtime_cache[key]
        except KeyError as error:
            raise KeyError(f"Ресурс не найден в runtime-index: {key}") from error

    @classmethod
    def get__cache_static(cls):
        """Совместимость со старым API: вернуть первый кадр каждого ресурса."""
        return {
            key: frames[0]
            for key, frames in cls._cache_frames.items()
            if frames
        }

    @classmethod
    def get__cache_anim(cls):
        """Совместимость со старым API: вернуть все списки кадров."""
        return cls._cache_frames

    @classmethod
    def add_to_cache_static(cls, path):
        """Совместимость: загрузить PNG из папки как списки кадров."""
        for file_path in cls.get_files_in_dir(path):
            cls.add_to_cache_frames_file(file_path)
        return cls.get__cache_static()

    @classmethod
    def add_to_cache_anim(cls, path):
        """Совместимость: загрузить PNG из папки как списки кадров."""
        for file_path in cls.get_files_in_dir(path):
            cls.add_to_cache_frames_file(file_path)
        return cls._cache_frames

    @classmethod
    def add_to_cache_static_file(cls, file_path, resource_key=None):
        """Совместимость: загрузить один PNG и вернуть static-view кэша."""
        cls.add_to_cache_frames_file(file_path, resource_key)
        return cls.get__cache_static()

    @classmethod
    def add_to_cache_anim_file(cls, file_path, resource_key=None):
        """Совместимость: загрузить один PNG и вернуть frame-cache."""
        cls.add_to_cache_frames_file(file_path, resource_key)
        return cls._cache_frames

    @classmethod
    def add_to_cache_frames_file(cls, file_path, resource_key=None):
        """Загрузить один PNG, нарезать его на кадры и положить в общий кэш."""
        key = resource_key or cls.resolve_resource_key(file_path)
        if key in cls._cache_frames:
            return cls._cache_frames

        record = cls.get_or_create_record(file_path, key)
        surface = pygame.image.load(record.path).convert_alpha()
        cls._cache_frames[key] = [
            surface.subsurface(frame_rect).copy()
            for frame_rect in cls.get_frame_grid(record)
        ]
        return cls._cache_frames

    @classmethod
    def get_static(cls, key_or_path):
        """Совместимость: вернуть первый кадр ресурса."""
        frames = cls.get_frames(key_or_path)
        if not frames:
            raise KeyError(f"Ресурс не содержит кадров: {key_or_path}")
        return frames[0]

    @classmethod
    def get_animation(cls, key_or_path):
        """Совместимость: вернуть список кадров ресурса."""
        return cls.get_frames(key_or_path)

    @classmethod
    def get_frames(cls, key_or_path):
        """Получить ресурс как список кадров по resource_key или пути."""
        key = cls.resolve_resource_key(key_or_path)
        try:
            return cls._cache_frames[key]
        except KeyError as error:
            raise KeyError(f"Ресурс не загружен в frame-кэш ResourceManager: {key}") from error

    @classmethod
    def resolve_resource_key(cls, key_or_path):
        """Преобразовать resource_key или путь файла в ключ runtime-index."""
        if key_or_path in cls._runtime_cache:
            return key_or_path

        cache_key = cls.get_cache_key(key_or_path)
        for record in cls._runtime_cache.values():
            if cls.get_cache_key(record.path) == cache_key:
                return record.key

        return key_or_path

    @staticmethod
    def get_cache_key(path):
        """Построить технический ключ для сравнения путей."""
        return os.path.normcase(os.path.abspath(path))

    @classmethod
    def get_or_create_record(cls, file_path, resource_key=None):
        """Вернуть существующий record или создать fallback-record для прямой загрузки."""
        if resource_key and resource_key in cls._runtime_cache:
            return cls._runtime_cache[resource_key]

        assets_dir = cls._assets_dir or os.path.dirname(os.path.abspath(file_path))
        relative_path = os.path.relpath(file_path, assets_dir)
        key = resource_key or cls.build_resource_key(relative_path)
        entry = cls.create_default_manifest_entry(file_path, assets_dir)
        return cls.create_record(key, entry, assets_dir)

    @classmethod
    def create_record(cls, resource_key, entry, assets_dir):
        """Создать ResourceRecord из записи manifest."""
        relative_path = cls.normalize_manifest_path(entry["path"])
        file_path = os.path.abspath(os.path.join(assets_dir, relative_path))
        frame_width = int(entry["frame_width"])
        frame_height = int(entry["frame_height"])

        with Image.open(file_path) as image:
            original_size = image.size

        rows = cls.calculate_rows(file_path, original_size, frame_width, frame_height)

        return ResourceRecord(
            key=resource_key,
            path=file_path,
            relative_path=relative_path,
            file_name=os.path.basename(file_path),
            original_size=original_size,
            frame_width=frame_width,
            frame_height=frame_height,
            rows=rows,
        )

    @classmethod
    def calculate_rows(cls, file_path, image_size, frame_width, frame_height):
        """Посчитать rows и проверить, что PNG можно нарезать без остатка."""
        image_width, image_height = image_size
        if frame_width != image_width:
            raise ValueError(
                f"Некорректный manifest для {file_path}: frame_width={frame_width}, "
                f"но ширина изображения {image_width}. Сейчас поддерживается одна колонка."
            )
        if frame_height <= 0:
            raise ValueError(f"Некорректный manifest для {file_path}: frame_height должен быть > 0.")
        if image_height % frame_height != 0:
            raise ValueError(
                f"Некорректный manifest для {file_path}: высота изображения "
                f"{image_height} не делится на frame_height={frame_height}."
            )
        return image_height // frame_height

    @staticmethod
    def get_frame_grid(record):
        """Построить вертикальную сетку кадров по ResourceRecord."""
        return [
            pygame.Rect(0, row * record.frame_height, record.frame_width, record.frame_height)
            for row in range(record.rows)
        ]

    @staticmethod
    def get_png_files(directory):
        """Рекурсивно вернуть PNG-файлы из directory, кроме служебных файлов."""
        png_files = []
        for root, _dirs, files in os.walk(directory):
            for file_name in files:
                if file_name.lower().endswith(".png"):
                    png_files.append(os.path.join(root, file_name))
        return sorted(png_files)

    @staticmethod
    def get_files_in_dir(directory, extension=".png"):
        """Вернуть PNG-файлы только из одной папки. Оставлено для совместимости."""
        return sorted(
            os.path.join(directory, filename)
            for filename in os.listdir(directory)
            if filename.lower().endswith(extension)
        )

    @classmethod
    def get_manifest_path(cls, assets_dir):
        """Вернуть путь к resource_manifest.json."""
        return os.path.join(os.path.abspath(assets_dir), cls.MANIFEST_FILE_NAME)

    @classmethod
    def load_or_generate_manifest(cls, assets_dir):
        """Загрузить manifest или создать временный manifest из всех PNG."""
        manifest_path = cls.get_manifest_path(assets_dir)
        if os.path.exists(manifest_path):
            return cls.load_manifest(assets_dir)
        return cls.generate_manifest(assets_dir)

    @classmethod
    def load_manifest(cls, assets_dir):
        """Прочитать resource_manifest.json."""
        manifest_path = cls.get_manifest_path(assets_dir)
        with open(manifest_path, "r", encoding="utf-8") as file:
            manifest = json.load(file)
        manifest.setdefault("resources", {})
        return manifest

    @classmethod
    def save_manifest(cls, assets_dir, manifest):
        """Сохранить resource_manifest.json."""
        manifest_path = cls.get_manifest_path(assets_dir)
        manifest = cls.normalize_manifest(manifest)
        with open(manifest_path, "w", encoding="utf-8") as file:
            json.dump(manifest, file, ensure_ascii=False, indent=2)
            file.write("\n")
        return manifest

    @classmethod
    def generate_manifest(cls, assets_dir):
        """Создать manifest из всех PNG, считая каждый PNG одним кадром."""
        assets_dir = os.path.abspath(assets_dir)
        resources = {}
        for file_path in cls.get_png_files(assets_dir):
            entry = cls.create_default_manifest_entry(file_path, assets_dir)
            resource_key = cls.build_resource_key(entry["path"])
            resources[resource_key] = entry
        return cls.normalize_manifest({"resources": resources})

    @classmethod
    def create_default_manifest_entry(cls, file_path, assets_dir):
        """Создать manifest-запись для PNG по умолчанию."""
        with Image.open(file_path) as image:
            width, height = image.size
        return {
            "path": os.path.relpath(file_path, assets_dir).replace("\\", "/"),
            "frame_width": width,
            "frame_height": height,
        }

    @classmethod
    def normalize_manifest(cls, manifest):
        """Привести manifest к стабильному виду перед сохранением."""
        resources = manifest.get("resources", {})
        normalized = {}
        for resource_key in sorted(resources):
            entry = resources[resource_key]
            normalized[resource_key] = {
                "path": cls.normalize_manifest_path(entry["path"]),
                "frame_width": int(entry["frame_width"]),
                "frame_height": int(entry["frame_height"]),
            }
        return {"resources": normalized}

    @staticmethod
    def normalize_manifest_path(path):
        """Нормализовать путь внутри assets/."""
        return str(path).replace("\\", "/")

    @staticmethod
    def build_resource_key(relative_path):
        """Построить человекочитаемый ключ по структуре assets/."""
        without_ext, _ext = os.path.splitext(relative_path)
        parts = []
        for part in without_ext.replace("\\", "/").split("/"):
            clean = part.strip().replace(" ", "_")
            if clean:
                parts.append(clean)
        return ".".join(parts)
