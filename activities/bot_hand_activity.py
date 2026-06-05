"""Каркас Activity для визуальной руки бота.

BotHandActivity - долгоживущий режим, привязанный к одному Frame руки.
На вход он получает только визуальные данные: frame, resource_key рубашки и
card_count. Жизненный цикл реальных карт остается в GameController.
"""

import math

import pygame

from activities.base_activity import Activity
from group import Group


class BotHandActivity(Activity):
    """Режим веера закрытых карт игрока/бота."""

    def __init__(
        self,
        frame,
        resource_manager=None,
        resource_key=None,
        card_count=0,
        group_id_prefix=None,
        max_total_angle=180,
        reference_card_count=9,
        radius=0,
        orientation_degrees=90,
        center_offset=(30, 0),
    ):
        super().__init__(duration=0.0)
        self.frame = frame
        self.resource_manager = resource_manager
        self.resource_key = resource_key
        self.card_count = max(0, int(card_count))
        self.group_id_prefix = group_id_prefix or f"{self.frame.id}.bot_hand"
        self.max_total_angle = float(max_total_angle)
        self.reference_card_count = max(2, int(reference_card_count))
        self.radius = float(radius)
        self.orientation_degrees = float(orientation_degrees)
        self.center_offset = tuple(center_offset)
        self.generated_groups = []

    def start(self):
        """Запустить режим руки и подготовить первый визуальный snapshot."""
        super().start()
        self.sync_visual_groups()
        self.apply_fan_layout()

    def update(self, dt):
        """Обновить режим руки.

        Пошаговый сценарий будущей реализации:

        1. Получить актуальный card_count из команды экрана или контроллера.
        2. Синхронизировать число visual-only Group с card_count.
        3. Пересчитать геометрию веера внутри self.frame.
        4. Запустить/обновить короткие Action для плавного перемещения.
        5. Обновить hover/selection, если режим руки интерактивен.

        Пока Activity применяет позиции напрямую. Позже этот шаг можно
        заменить запуском коротких MoveGroupAction.
        """
        _ = dt
        if not self.started:
            self.start()

    def set_card_count(self, card_count):
        """Обновить число закрытых карт, которое нужно отобразить."""
        self.card_count = max(0, int(card_count))
        self.sync_visual_groups()
        self.apply_fan_layout()

    def apply_fixture(self, fixture):
        """Применить dev fixture без участия правил игры.

        Поддерживаемые поля:
        - resource_key;
        - card_count;

        Остальная геометрия веера является внутренней кухней Activity и не
        входит в публичную команду контроллера.
        """
        if not fixture:
            return

        resource_key = fixture.get("resource_key", self.resource_key)
        if resource_key != self.resource_key:
            self.clear_generated_groups()
            self.resource_key = resource_key

        self.set_card_count(fixture.get("card_count", self.card_count))

    def sync_visual_groups(self):
        """Синхронизировать generated Group с card_count.

        Если групп меньше card_count, создает недостающие Group из resource_key.
        Если групп больше card_count, удаляет лишние Group из frame и владения.
        """
        while len(self.generated_groups) < self.card_count:
            self.add_generated_group(len(self.generated_groups))

        while len(self.generated_groups) > self.card_count:
            group = self.generated_groups.pop()
            self.frame.remove_group_id(group.id)
            self.frame.group_origins.pop(group.id, None)

    def apply_fan_layout(self):
        """Рассчитать и применить веер закрытых карт внутри frame.

        Алгоритм:
        - общий угол делится на промежутки между картами;
        - угол каждой карты центрируется относительно центральной оси;
        - pivot карты - нижний край по центру;
        - group ставится так, чтобы pivot попал в рассчитанную точку веера.
        """
        count = len(self.generated_groups)
        if count <= 0:
            return

        frame_rect = self.frame.rect
        center_x, center_y = self.get_fan_center(frame_rect)
        occupied_angle, angle_step = self.calculate_fan_angles(count)

        for index, group in enumerate(self.generated_groups):
            local_angle = -occupied_angle / 2 + index * angle_step
            angle = self.orientation_degrees + local_angle
            pivot_x, pivot_y = self.calculate_pivot_position(center_x, center_y, angle)
            self.apply_card_transform(group, angle, (pivot_x, pivot_y))
            self.frame.group_origins[group.id] = group.rect.topleft

    def calculate_fan_angles(self, count):
        """Return total occupied angle and step for count cards.

        Nine cards occupy half a circle. Larger hands are compressed into the
        same half-circle span.
        """
        if count <= 1:
            return 0.0, 0.0

        reference_step = self.max_total_angle / (self.reference_card_count - 1)
        if count <= self.reference_card_count:
            return reference_step * (count - 1), reference_step

        compressed_step = self.max_total_angle / (count - 1)
        return self.max_total_angle, compressed_step

    def get_fan_center(self, frame_rect):
        """Вернуть точку схода веера в координатах экрана."""
        return (
            frame_rect.centerx + int(self.center_offset[0]),
            frame_rect.centery + int(self.center_offset[1]),
        )

    def calculate_pivot_position(self, center_x, center_y, angle_degrees):
        """Перевести угол карты в координату pivot по радиусу веера."""
        radians = math.radians(angle_degrees)
        return (
            center_x + self.radius * math.sin(radians),
            center_y - self.radius * math.cos(radians),
        )

    def apply_card_transform(self, group, angle_degrees, pivot_position):
        """Повернуть карту вокруг нижнего центра и поставить в pivot."""
        base_surface = group._bot_hand_base_frames[0]
        rotated_surface = pygame.transform.rotate(base_surface, -angle_degrees)

        group.layers[0].frames = [rotated_surface]
        group.layers[0].position = (0, 0)
        group.set_scale_factor(1.0)

        pivot_offset = self.calculate_rotated_pivot_offset(
            base_surface.get_size(),
            rotated_surface.get_size(),
            angle_degrees,
        )
        group.set_rect((
            round(pivot_position[0] - pivot_offset[0]),
            round(pivot_position[1] - pivot_offset[1]),
            rotated_surface.get_width(),
            rotated_surface.get_height(),
        ))

    @staticmethod
    def calculate_rotated_pivot_offset(scaled_size, rotated_size, angle_degrees):
        """Найти pivot нижнего центра внутри повернутой surface."""
        _, scaled_height = scaled_size
        center = pygame.Vector2(rotated_size[0] / 2, rotated_size[1] / 2)
        bottom_center_from_source_center = pygame.Vector2(0, scaled_height / 2)
        rotated_vector = bottom_center_from_source_center.rotate(angle_degrees)
        pivot = center + rotated_vector
        return pivot.x, pivot.y

    def add_generated_group(self, index):
        """Создать одну visual-only Group рубашки карты."""
        if self.resource_manager is None:
            raise RuntimeError("BotHandActivity requires resource_manager")
        if not self.resource_key:
            raise RuntimeError("BotHandActivity requires resource_key")

        group_id = f"{self.group_id_prefix}.{index}"
        group = Group.create_group(
            group_id,
            (("card_back", self.resource_key),),
            resource_manager=self.resource_manager,
        )
        group._bot_hand_base_frames = tuple(frame.copy() for frame in group.layers[0].frames)
        self.generated_groups.append(group)
        self.frame.add_group_id(group.id)
        return group

    def draw(self, screen):
        """Отрисовать generated visual-only Group, которыми владеет Activity."""
        for group in self.generated_groups:
            group.draw(screen)

    def clear_generated_groups(self):
        """Удалить все generated visual-only Group из frame и владения."""
        for group in self.generated_groups:
            self.frame.remove_group_id(group.id)
            self.frame.group_origins.pop(group.id, None)
        self.generated_groups = []

    def is_finished(self):
        """Рука бота - долгоживущий режим, сама по времени не завершается."""
        return self._finished

    def finish(self):
        """Завершить режим и удалить generated visual-only Group.

        Жизненный цикл игровых сущностей при этом не меняется.
        """
        self.clear_generated_groups()
        super().finish()
