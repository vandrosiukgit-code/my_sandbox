"""Загрузка, масштабирование и runtime-кэш графических ресурсов."""

import ast
import os
from dataclasses import dataclass
from typing import Optional

import pygame
from PIL import Image


@dataclass
class ResourceRecord:
    """Описание одного ресурса в runtime-кэше."""

    key: str
    path: str
    relative_path: str
    file_name: str
    resource_type: str
    original_size: tuple[int, int]
    scaled_size: tuple[int, int]
    target_height: Optional[int] = None
    rows: Optional[int] = None
    columns: Optional[int] = None
    target_frame_height: Optional[int] = None

    def to_payload(self):
        """Вернуть словарь для ResourcePicker и будущего GuiActor API."""
        return {
            "resource_key": self.key,
            "resource_type": self.resource_type,
            "path": self.path,
            "relative_path": self.relative_path,
            "file_name": self.file_name,
            "original_size": self.original_size,
            "scaled_size": self.scaled_size,
            "target_height": self.target_height,
            "rows": self.rows,
            "columns": self.columns,
            "target_frame_height": self.target_frame_height,
        }


class ResourceManager:
    """Общий низкоуровневый склад графических ресурсов проекта.

    Контракт ResourceManager:

    - рекурсивно сканирует корневую папку assets/;
    - строит runtime-index: `resource_key -> ResourceRecord`;
    - отдельно загружает pygame.Surface и кадры spritesheet;
    - не знает о GuiActor, GameScreen, Activity и правилах игры;
    - отдает готовые Surface/frames фабрике actor-ов.

    Важно: методы, которые вызывают `convert_alpha()`, требуют уже созданный
    pygame display. Для dev tools нужно использовать metadata-only режим.
    """

    _cache_static = {}
    _cache_anim = {}
    _runtime_cache = {}
    _assets_dir = None
    _static_info = {}
    _animation_info = {}

    @classmethod
    def build_cache(cls, assets_dir, load_surfaces=True):
        """Построить runtime-кэш для всех PNG внутри assets_dir.

        Args:
            assets_dir: Корневая папка ресурсов.
            load_surfaces: Загружать ли pygame.Surface/кадры. Для dev tools
                можно оставить False, чтобы не требовать pygame.display.
        """
        cls.clear_cache()
        cls._assets_dir = os.path.abspath(assets_dir)
        cls._static_info = cls.read_all_static_info(cls._assets_dir)
        cls._animation_info = cls.read_all_animation_info(cls._assets_dir)

        for file_path in cls.get_png_files(cls._assets_dir):
            record = cls.create_record(file_path, cls._assets_dir)
            cls._runtime_cache[record.key] = record

            if load_surfaces:
                if record.resource_type == "animation":
                    cls.add_to_cache_anim_file(file_path, record.key)
                else:
                    cls.add_to_cache_static_file(file_path, record.key)

        return cls._runtime_cache

    @classmethod
    def build_index(cls, assets_dir):
        """Построить только runtime-index без загрузки pygame.Surface.

        Этот метод предназначен для dev tools и других сценариев, где нужен
        список ресурсов, ключи, размеры и metadata, но pygame display еще не
        создан. Например, `tools/resource_picker.py` должен работать именно
        через этот путь.
        """
        return cls.build_cache(assets_dir, load_surfaces=False)

    @classmethod
    def build_runtime_cache(cls, assets_dir):
        """Построить runtime-index и загрузить Surface/frames.

        Этот метод предназначен для игрового запуска после инициализации
        pygame display. Он оставляет старое поведение `build_cache(...,
        load_surfaces=True)`, но название лучше отражает смысл.
        """
        return cls.build_cache(assets_dir, load_surfaces=True)

    @classmethod
    def load_surfaces_from_index(cls):
        """Загрузить Surface/frames для уже построенного runtime-index.

        Метод полезен, если сначала был построен metadata-only index, а затем
        pygame display стал доступен и нужно догрузить реальные поверхности.
        """
        for record in cls._runtime_cache.values():
            if record.resource_type == "animation":
                cls.add_to_cache_anim_file(record.path, record.key)
            else:
                cls.add_to_cache_static_file(record.path, record.key)
        return cls._cache_static, cls._cache_anim

    @classmethod
    def clear_cache(cls):
        """Очистить все runtime-структуры.

        После очистки ResourceManager не содержит ни metadata-index, ни
        загруженных Surface/frames. Путь assets и info-таблицы тоже считаются
        недействительными.
        """
        cls._cache_static = {}
        cls._cache_anim = {}
        cls._runtime_cache = {}
        cls._assets_dir = None
        cls._static_info = {}
        cls._animation_info = {}

    @classmethod
    def get_runtime_cache(cls):
        """Вернуть структуру runtime-кэша key -> ResourceRecord."""
        return cls._runtime_cache

    @classmethod
    def get_runtime_payloads(cls):
        """Вернуть metadata runtime-index в виде словарей.

        Это удобный API для dev tools: интерфейс может показать ключи,
        размеры, пути и параметры кадров без доступа к pygame.Surface.
        """
        return {
            key: record.to_payload()
            for key, record in cls._runtime_cache.items()
        }

    @classmethod
    def get_record(cls, key_or_path):
        """Получить ResourceRecord по resource key или пути файла."""
        if key_or_path in cls._runtime_cache:
            return cls._runtime_cache[key_or_path]

        cache_key = cls.get_cache_key(key_or_path)
        for record in cls._runtime_cache.values():
            if cls.get_cache_key(record.path) == cache_key:
                return record
        raise KeyError(f"Ресурс не найден в runtime-кэше: {key_or_path}")

    @classmethod
    def get__cache_static(cls):
        """Точка подключения к статическим ресурсам в RAM."""
        return cls._cache_static

    @classmethod
    def get__cache_anim(cls):
        """Точка подключения к анимированным ресурсам в RAM."""
        return cls._cache_anim

    @staticmethod
    def get_png_files(directory):
        """Рекурсивно вернуть PNG-файлы из directory."""
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
    def add_to_cache_static(cls, path):
        """Загрузить все статические PNG из одной папки."""
        for file_path in cls.get_files_in_dir(path):
            cls.add_to_cache_static_file(file_path)
        return cls._cache_static

    @classmethod
    def add_to_cache_static_file(cls, file_path, resource_key=None):
        """Загрузить один статический PNG в общий кэш."""
        key = resource_key or cls.resolve_resource_key(file_path)
        if key in cls._cache_static:
            return cls._cache_static

        scale_factor = cls.get_scale_factor(file_path)
        surface = pygame.image.load(file_path).convert_alpha()
        scaled_size = cls.get_scaled_size(surface.get_size(), scale_factor)
        cls._cache_static[key] = pygame.transform.smoothscale(surface, scaled_size)
        return cls._cache_static

    @classmethod
    def add_to_cache_anim(cls, path):
        """Загрузить все PNG-анимации из одной папки."""
        for file_path in cls.get_files_in_dir(path):
            cls.add_to_cache_anim_file(file_path)
        return cls._cache_anim

    @classmethod
    def add_to_cache_anim_file(cls, file_path, resource_key=None):
        """Загрузить один spritesheet в общий кэш анимаций."""
        key = resource_key or cls.resolve_resource_key(file_path)
        if key in cls._cache_anim:
            return cls._cache_anim

        scale_factor = cls.get_animation_scale_factor(file_path)
        surface = pygame.image.load(file_path).convert_alpha()
        scaled_size = cls.get_scaled_size(surface.get_size(), scale_factor)
        surface = pygame.transform.smoothscale(surface, scaled_size)
        cls._cache_anim[key] = [
            surface.subsurface(frame_rect).copy()
            for frame_rect in cls.get_frame_grid(file_path, surface.get_size())
        ]
        return cls._cache_anim

    @classmethod
    def get_static(cls, key_or_path):
        """Получить статическую поверхность по resource key или пути.

        Этот метод вызывается фабрикой actor-ов. Если ресурс не загружен,
        ошибка явно говорит, что нужно сначала построить runtime-cache с
        surfaces или вызвать `load_surfaces_from_index()`.
        """
        key = cls.resolve_resource_key(key_or_path)
        try:
            return cls._cache_static[key]
        except KeyError as error:
            raise KeyError(f"Статический ресурс не загружен в Surface-кэш: {key}") from error

    @classmethod
    def get_animation(cls, key_or_path):
        """Получить список кадров анимации по resource key или пути."""
        key = cls.resolve_resource_key(key_or_path)
        try:
            return cls._cache_anim[key]
        except KeyError as error:
            raise KeyError(f"Анимация не загружена в frame-кэш: {key}") from error

    @classmethod
    def resolve_resource_key(cls, key_or_path):
        """Преобразовать resource key или путь файла в ключ runtime-кэша."""
        if key_or_path in cls._runtime_cache:
            return key_or_path

        cache_key = cls.get_cache_key(key_or_path)
        for record in cls._runtime_cache.values():
            if cls.get_cache_key(record.path) == cache_key:
                return record.key

        if cls._assets_dir and os.path.exists(key_or_path):
            return cls.build_resource_key(os.path.relpath(key_or_path, cls._assets_dir))
        return cls.get_cache_key(key_or_path)

    @staticmethod
    def get_cache_key(path):
        """Построить технический ключ для сравнения путей."""
        return os.path.normcase(os.path.abspath(path))

    @classmethod
    def create_record(cls, file_path, assets_dir):
        """Создать ResourceRecord для PNG-файла."""
        file_name = os.path.basename(file_path)
        relative_path = os.path.relpath(file_path, assets_dir)
        resource_key = cls.build_resource_key(relative_path)

        with Image.open(file_path) as image:
            original_size = image.size

        animation_info = cls._animation_info.get(file_name)
        target_height = cls._static_info.get(file_name)

        if animation_info:
            rows = animation_info["rows"]
            columns = animation_info["columns"]
            target_frame_height = animation_info["target_frame_height"]
            scale_factor = cls.get_animation_scale_factor(file_path)
            resource_type = "animation"
        else:
            rows = None
            columns = None
            target_frame_height = None
            scale_factor = cls.get_scale_factor(file_path)
            resource_type = "static" if target_height is not None else "unknown"

        return ResourceRecord(
            key=resource_key,
            path=os.path.abspath(file_path),
            relative_path=relative_path,
            file_name=file_name,
            resource_type=resource_type,
            original_size=original_size,
            scaled_size=cls.get_scaled_size(original_size, scale_factor),
            target_height=target_height,
            rows=rows,
            columns=columns,
            target_frame_height=target_frame_height,
        )

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

    @classmethod
    def get_scale_factor(cls, path):
        """Посчитать масштаб для статической картинки."""
        target_height = cls.get_target_height(path)
        if target_height is None:
            return 1.0

        with Image.open(path) as image:
            return target_height / image.height

    @classmethod
    def get_animation_scale_factor(cls, path):
        """Посчитать масштаб spritesheet по целевой высоте одного кадра."""
        rows, _columns, target_frame_height = cls.get_animation_info(path)
        with Image.open(path) as image:
            source_frame_height = image.height / rows
        return target_frame_height / source_frame_height

    @classmethod
    def get_frame_grid(cls, path, image_size=None):
        """Построить сетку кадров для spritesheet."""
        rows, columns = cls.get_animation_grid_size(path)
        if image_size is None:
            with Image.open(path) as image:
                width, height = image.size
        else:
            width, height = image_size
        frame_width = width // columns
        frame_height = height // rows

        return [
            pygame.Rect(column * frame_width, row * frame_height, frame_width, frame_height)
            for row in range(rows)
            for column in range(columns)
        ]

    @staticmethod
    def get_scaled_size(size, scale_factor):
        """Вернуть новый размер surface после применения scale_factor."""
        width, height = size
        return max(1, round(width * scale_factor)), max(1, round(height * scale_factor))

    @classmethod
    def get_target_height(cls, path):
        """Найти целевую высоту статического PNG."""
        file_name = os.path.basename(path)
        if file_name in cls._static_info:
            return cls._static_info[file_name]

        info_path = os.path.join(os.path.dirname(path), "static_info.txt")
        if not os.path.exists(info_path):
            return None

        for item in cls.read_info_file(info_path):
            if len(item) == 2 and item[0] == file_name:
                return int(item[1])
        return None

    @classmethod
    def get_animation_grid_size(cls, path):
        """Вернуть количество строк и столбцов для spritesheet."""
        rows, columns, _target_frame_height = cls.get_animation_info(path)
        return int(rows), int(columns)

    @classmethod
    def get_animation_info(cls, path):
        """Найти запись анимации по имени файла."""
        file_name = os.path.basename(path)
        if file_name in cls._animation_info:
            info = cls._animation_info[file_name]
            return info["rows"], info["columns"], info["target_frame_height"]

        info_path = os.path.join(os.path.dirname(path), "anim_info.txt")
        if not os.path.exists(info_path):
            raise FileNotFoundError(f"Не найден файл с данными анимации: {info_path}")

        for item in cls.read_info_file(info_path):
            if len(item) == 4 and item[0] == file_name:
                _filename, rows, columns, target_frame_height = item
                return int(rows), int(columns), int(target_frame_height)

        raise ValueError(f"В anim_info.txt нет данных для файла: {file_name}")

    @classmethod
    def read_all_static_info(cls, assets_dir):
        """Прочитать static_info.txt во всех подпапках assets/."""
        info = {}
        for path in cls.find_info_files(assets_dir, "static_info.txt"):
            for item in cls.read_info_file(path):
                if len(item) == 2:
                    file_name, target_height = item
                    info[file_name] = int(target_height)
        return info

    @classmethod
    def read_all_animation_info(cls, assets_dir):
        """Прочитать anim_info.txt во всех подпапках assets/."""
        info = {}
        for path in cls.find_info_files(assets_dir, "anim_info.txt"):
            for item in cls.read_info_file(path):
                if len(item) == 4:
                    file_name, rows, columns, target_frame_height = item
                    info[file_name] = {
                        "rows": int(rows),
                        "columns": int(columns),
                        "target_frame_height": int(target_frame_height),
                    }
        return info

    @staticmethod
    def find_info_files(root_dir, file_name):
        """Найти info-файлы по имени."""
        for root, _dirs, files in os.walk(root_dir):
            if file_name in files:
                yield os.path.join(root, file_name)

    @staticmethod
    def read_info_file(path):
        """Прочитать info-файл, где каждая строка - Python tuple."""
        items = []
        with open(path, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                items.append(ast.literal_eval(line))
        return items
