import ast
import os

import pygame
from PIL import Image


class ResourceManager:
    _cache_static = {}  # Общий для всего проекта
    _cache_anim = {}  # Общий для всего проекта

    @classmethod
    def get__cache_static(cls):
        """Точка подключения к статическим ресурсам в RAM."""
        return cls._cache_static

    @classmethod
    def get__cache_anim(cls):
        """Точка подключения к анимированным ресурсам в RAM."""
        return cls._cache_anim

    @staticmethod
    def get_files_in_dir(directory, extension=".png"):
        """Возвращает список полных путей к PNG файлам в папке."""
        return sorted(
            os.path.join(directory, filename)
            for filename in os.listdir(directory)
            if filename.lower().endswith(extension)
        )

    @classmethod
    def add_to_cache_static(cls, path):
        # 1. Открывает папку и получает список путей к PNG файлам.
        # 2. Проверяет в "_cache_static", есть ли такой объект в кэше.
        # 3. Если объекта нет, масштабирует PNG и кладет pygame.Surface в общий кэш.
        for file_path in cls.get_files_in_dir(path):
            key = cls.get_cache_key(file_path)
            if key in cls._cache_static:
                continue

            scale_factor = cls.get_scale_factor(file_path)
            surface = pygame.image.load(file_path).convert_alpha()
            scaled_size = cls.get_scaled_size(surface.get_size(), scale_factor)
            cls._cache_static[key] = pygame.transform.smoothscale(surface, scaled_size)

        return cls._cache_static

    @classmethod
    def add_to_cache_anim(cls, path):
        # 1. Открывает папку и получает список путей к PNG файлам.
        # 2. Проверяет в "_cache_anim", есть ли такая анимация в кэше.
        # 3. Если объекта нет, масштабирует spritesheet, режет его на кадры и кладет список кадров в общий кэш.
        for file_path in cls.get_files_in_dir(path):
            key = cls.get_cache_key(file_path)
            if key in cls._cache_anim:
                continue

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
    def get_static(cls, path):
        return cls._cache_static[cls.get_cache_key(path)]

    @classmethod
    def get_animation(cls, path):
        return cls._cache_anim[cls.get_cache_key(path)]

    @staticmethod
    def get_cache_key(path):
        return os.path.normcase(os.path.abspath(path))

    @staticmethod
    def get_scale_factor(path):
        # 1. Берет для PNG-файла его реальный размер по высоте.
        # 2. Берет из static_info.txt целевое значение высоты для конкретного PNG.
        # 3. Вычисляет фактор масштаба: целевая высота / реальная высота.
        target_height = ResourceManager.get_target_height(path)
        if target_height is None:
            return 1.0

        with Image.open(path) as image:
            return target_height / image.height

    @staticmethod
    def get_animation_scale_factor(path):
        # 1. Берет высоту PNG и количество рядов кадров.
        # 2. Берет из anim_info.txt целевую высоту одного кадра.
        # 3. Вычисляет фактор масштаба: целевая высота кадра / реальная высота кадра.
        rows, _columns, target_frame_height = ResourceManager.get_animation_info(path)
        with Image.open(path) as image:
            source_frame_height = image.height / rows
        return target_frame_height / source_frame_height

    @staticmethod
    def get_frame_grid(path, image_size=None):
        # 1. Берет размер PNG.
        # 2. Берет из anim_info.txt количество рядов и столбцов.
        # 3. Строит решетку pygame.Rect для нарезки кадров.
        rows, columns = ResourceManager.get_animation_grid_size(path)
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
        width, height = size
        return max(1, round(width * scale_factor)), max(1, round(height * scale_factor))

    @staticmethod
    def get_target_height(path):
        info_path = os.path.join(os.path.dirname(path), "static_info.txt")
        if not os.path.exists(info_path):
            return None

        filename = os.path.basename(path)
        for item in ResourceManager.read_info_file(info_path):
            if len(item) == 2 and item[0] == filename:
                return int(item[1])
        return None

    @staticmethod
    def get_animation_grid_size(path):
        rows, columns, _target_frame_height = ResourceManager.get_animation_info(path)
        return int(rows), int(columns)

    @staticmethod
    def get_animation_info(path):
        info_path = os.path.join(os.path.dirname(path), "anim_info.txt")
        if not os.path.exists(info_path):
            raise FileNotFoundError(f"Не найден файл с данными анимации: {info_path}")

        filename = os.path.basename(path)
        for item in ResourceManager.read_info_file(info_path):
            if len(item) == 4 and item[0] == filename:
                _filename, rows, columns, target_frame_height = item
                return int(rows), int(columns), int(target_frame_height)

        raise ValueError(f"В anim_info.txt нет данных для файла: {filename}")

    @staticmethod
    def read_info_file(path):
        items = []
        with open(path, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                items.append(ast.literal_eval(line))
        return items
