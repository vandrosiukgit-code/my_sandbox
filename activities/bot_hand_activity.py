"""Каркас Activity для визуальной руки бота.

BotHandActivity - долгоживущий режим, привязанный к одному Frame руки.
На вход он получает только визуальные данные: frame, resource_key рубашки и
card_count. Жизненный цикл реальных карт остается в GameController.
"""

import math

import pygame

from activities.base_activity import Activity
from activities import card_visibility
from activities import normalizers
from game_screen import debug_overlay
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
        scale_factor=0.8,
        max_total_angle=160,
        reference_card_count=9,
        radius=0,
        orientation_degrees=90,
        center_offset=(50, 0),
        card_resource_provider=None,
        card_layer_name="card_back",
        debug_fan_rect=False,
        debug_fan_rect_color=(255, 232, 64),
    ):
        super().__init__(duration=0.0)
        self.frame = frame
        self.resource_manager = resource_manager
        self.resource_key = resource_key
        self.card_count = max(0, int(card_count))
        self.group_id_prefix = group_id_prefix or f"{self.frame.id}.bot_hand"
        self.scale_factor = self.normalize_scale_factor(scale_factor)
        self.max_total_angle = float(max_total_angle)
        self.reference_card_count = max(2, int(reference_card_count))
        self.radius = float(radius)
        self.orientation_degrees = float(orientation_degrees)
        self.center_offset = self.normalize_pair(center_offset)
        self.card_resource_provider = card_resource_provider
        self.card_layer_name = card_layer_name
        self.generated_groups = []
        self.group_hand_indices = {}
        self.group_card_ids = {}
        self.group_resource_keys = {}
        self.group_base_frames = {}
        self._last_layout_signature = None
        self.debug_fan_rect = bool(debug_fan_rect)
        self.debug_fan_rect_color = tuple(debug_fan_rect_color)

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
            return

        if self.get_layout_signature() != self._last_layout_signature:
            self.apply_fan_layout()

    def set_card_count(self, card_count):
        """Обновить число закрытых карт, которое нужно отобразить."""
        self.card_count = max(0, int(card_count))
        self.sync_visual_groups()
        self.apply_fan_layout()

    def prepare_cards(self, card_resource_keys, revealed_count=0):
        """Build final fan slots and conceal cards that have not landed yet."""
        keys = tuple(card_resource_keys)
        self.configure_card_resources(
            provider=lambda index: keys[index],
            layer_name=self.card_layer_name,
            card_count=len(keys),
        )
        for index, resource_key in enumerate(keys):
            if index < revealed_count:
                continue
            surface = self.resource_manager.get_frames(resource_key)[0]
            self.set_card_base_frames(index, [card_visibility.create_transparent_surface_like(surface)], apply_layout=False)
        self.apply_fan_layout()

    def prepare_incremental_cards(self, visible_cards, incoming_cards=()):
        """Keep bot hands incremental so each deal step targets the current fan size."""
        keys = tuple(visible_cards or ())
        _ = tuple(incoming_cards or ())
        self.configure_card_resources(
            provider=lambda index: keys[index],
            layer_name=self.card_layer_name,
            card_count=len(keys),
        )

    def append_revealed_card(self, resource_key):
        """Append one newly dealt bot card and rebuild the fan for the next step."""
        keys = tuple(self.get_card_resource_key(index) for index in range(self.card_count))
        keys = (*keys, resource_key)
        self.configure_card_resources(
            provider=lambda index: keys[index],
            layer_name=self.card_layer_name,
            card_count=len(keys),
        )
        return True

    def reveal_card(self, hand_index):
        resource_key = self.get_card_resource_key(hand_index)
        self.set_card_base_frames(hand_index, self.resource_manager.get_frames(resource_key))

    def set_card_base_frames(self, hand_index, frames, apply_layout=True):
        group = self.generated_groups[hand_index]
        self.group_base_frames[group.id] = list(frames)
        if apply_layout:
            self.apply_fan_layout()

    def get_prepared_card_screen_geometry(self, hand_index):
        return self.get_group_card_screen_geometry(self.generated_groups[hand_index])

    def get_projected_card_screen_geometry(self, hand_index, resource_key=None, card_count=None):
        projected_count = max(int(hand_index) + 1, len(self.generated_groups), int(card_count or 0))
        occupied_angle, angle_step = self.calculate_fan_angles(projected_count)
        local_angle = self.calculate_card_angle(hand_index, projected_count, occupied_angle, angle_step)
        angle = self.orientation_degrees + local_angle
        frame_rect = self.frame.content_rect
        center_x, center_y = self.get_fan_center(frame_rect)
        pivot_x, pivot_y = self.calculate_pivot_position(center_x, center_y, angle)
        base_surface = self.get_reference_card_surface(resource_key)
        scaled_surface = self.scale_surface(base_surface)
        rotated_surface = pygame.transform.rotate(scaled_surface, -angle)
        pivot_offset = self.calculate_rotated_pivot_offset(
            scaled_surface.get_size(),
            rotated_surface.get_size(),
            angle,
        )
        offset_scale = self.get_activity_local_scale()
        local_rect = pygame.Rect(
            int(round(pivot_x - pivot_offset[0] * offset_scale)),
            int(round(pivot_y - pivot_offset[1] * offset_scale)),
            rotated_surface.get_width(),
            rotated_surface.get_height(),
        )
        local_center = local_rect.center
        screen_center = self.frame.to_screen(local_center) if hasattr(self.frame, "to_screen") else local_center
        scale = self.get_frame_screen_scale()
        return {
            "center": tuple(screen_center),
            "size": (
                max(1, int(round(rotated_surface.get_width() * scale))),
                max(1, int(round(rotated_surface.get_height() * scale))),
            ),
            "angle_degrees": float(angle),
        }

    def configure_card_resources(self, provider=None, layer_name=None, card_count=None):
        """Configure the public resource contract used for generated cards."""
        should_sync = self.started or bool(self.generated_groups)
        resources_changed = (
            provider is not self.card_resource_provider
            or (layer_name is not None and layer_name != self.card_layer_name)
        )
        self.card_resource_provider = provider
        if layer_name is not None:
            self.card_layer_name = layer_name
        if card_count is not None:
            self.card_count = max(0, int(card_count))
        if resources_changed:
            self.clear_generated_groups()
        if should_sync:
            self.sync_visual_groups()
            self.apply_fan_layout()

    def set_resource_key(self, resource_key):
        """Set the card-back resource key and rebuild generated groups if needed."""
        if resource_key == self.resource_key:
            return
        should_sync = self.started or bool(self.generated_groups)
        self.resource_key = resource_key
        self.clear_generated_groups()
        if should_sync:
            self.sync_visual_groups()
            self.apply_fan_layout()

    def apply_fixture(self, fixture):
        """Применить dev fixture без участия правил игры.

        Поддерживаемые поля:
        - resource_key;
        - card_count;
        - scale_factor;
        - radius;
        - center_offset;

        Остальная геометрия веера является внутренней кухней Activity и не
        входит в публичную команду контроллера.
        """
        if not fixture:
            return

        if "resource_key" in fixture:
            self.set_resource_key(fixture["resource_key"])

        if "scale_factor" in fixture:
            self.scale_factor = self.normalize_scale_factor(fixture["scale_factor"])
        elif "scale" in fixture:
            self.scale_factor = self.normalize_scale_factor(fixture["scale"])
        self.radius = float(fixture.get("radius", self.radius))
        self.center_offset = self.normalize_pair(fixture.get("center_offset", self.center_offset))
        self.set_card_count(fixture.get("card_count", self.card_count))

    def sync_visual_groups(self):
        """Синхронизировать generated Group с card_count.

        Если групп меньше card_count, создает недостающие Group из resource_key.
        Если групп больше card_count, удаляет лишние Group из frame и владения.
        """
        for index, group in enumerate(tuple(self.generated_groups)):
            expected_key = self.get_card_resource_key(index)
            if self.group_resource_keys.get(group.id) != expected_key:
                self.clear_generated_groups()
                break

        while len(self.generated_groups) < self.card_count:
            self.add_generated_group(len(self.generated_groups))

        while len(self.generated_groups) > self.card_count:
            group = self.generated_groups.pop()
            self.frame.remove_group(group.id)
            self.group_hand_indices.pop(group.id, None)
            self.group_card_ids.pop(group.id, None)
            self.group_resource_keys.pop(group.id, None)
            self.group_base_frames.pop(group.id, None)

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
            self._last_layout_signature = self.get_layout_signature()
            return

        frame_rect = self.frame.content_rect
        center_x, center_y = self.get_fan_center(frame_rect)
        occupied_angle, angle_step = self.calculate_fan_angles(count)

        for index, group in enumerate(self.generated_groups):
            local_angle = self.calculate_card_angle(index, count, occupied_angle, angle_step)
            angle = self.orientation_degrees + local_angle
            pivot_x, pivot_y = self.calculate_pivot_position(center_x, center_y, angle)
            self.apply_card_transform(group, angle, (pivot_x, pivot_y))
        self._last_layout_signature = self.get_layout_signature()

    def calculate_card_angle(self, index, count, occupied_angle, angle_step):
        """Return card angle inside the old bot sector, assigned center-out like the player hand."""
        if angle_step == 0.0:
            return 0.0
        max_slot_angle = max(0.0, (occupied_angle - angle_step) / 2)
        return self.calculate_slot_position(index, count) * max_slot_angle

    def calculate_slot_position(self, index, count):
        """Return symmetric fan slots that grow from the center outward."""
        return self.get_center_out_slot_values(count)[index]

    def get_center_out_slot_values(self, count):
        count = max(0, int(count))
        if count <= 0:
            return ()
        if count == 1:
            return (0.0,)
        reference_count = max(count, int(self.reference_card_count))
        if reference_count % 2 == 0:
            reference_count += 1
        step = 2.0 / (reference_count - 1)
        values = []
        if count % 2 == 1:
            values.append(0.0)
            magnitudes = [step * offset for offset in range(1, reference_count // 2 + 1)]
        else:
            magnitudes = [step * (offset - 0.5) for offset in range(1, reference_count // 2 + 1)]
        for magnitude in magnitudes:
            values.extend((magnitude, -magnitude))
            if len(values) >= count:
                break
        return tuple(values[:count])

    def calculate_fan_angles(self, count):
        """Return total occupied angle and step for count cards.

        The reference hand defines card density: 9 cards occupy max_total_angle,
        so the reference step is max_total_angle / 9. Smaller hands keep that
        step and shrink the occupied sector. Larger hands keep max_total_angle
        and compress the step.
        """
        if count <= 1:
            return 0.0, 0.0

        reference_step = self.max_total_angle / self.reference_card_count
        if count <= self.reference_card_count:
            occupied_angle = reference_step * count
            return occupied_angle, reference_step

        compressed_step = self.max_total_angle / count
        return self.max_total_angle, compressed_step

    def get_fan_center(self, frame_rect):
        """Вернуть точку схода веера в локальных координатах frame."""
        local_scale = self.get_activity_local_scale()
        return (
            frame_rect.centerx + int(round(self.center_offset[0] * local_scale)),
            frame_rect.centery + int(round(self.center_offset[1] * local_scale)),
        )

    def calculate_pivot_position(self, center_x, center_y, angle_degrees):
        """Перевести угол карты в локальную координату pivot по радиусу веера."""
        radians = math.radians(angle_degrees)
        radius = self.radius * self.get_activity_local_scale()
        return (
            int(round(center_x + radius * math.sin(radians))),
            int(round(center_y - radius * math.cos(radians))),
        )

    def apply_card_transform(self, group, angle_degrees, pivot_position):
        """Повернуть карту вокруг нижнего центра и поставить в pivot."""
        base_surface = self.group_base_frames[group.id][0]
        rotated_surface = pygame.transform.rotate(base_surface, -angle_degrees)

        group.set_primary_layer_frames([rotated_surface], position=(0, 0))
        group.set_scale_factor(self.scale_factor)

        pivot_offset = self.calculate_rotated_pivot_offset(
            base_surface.get_size(),
            rotated_surface.get_size(),
            angle_degrees,
        )
        offset_scale = self.get_activity_local_scale()
        self.set_group_local_rect(
            group,
            (
                int(round(pivot_position[0] - pivot_offset[0] * offset_scale)),
                int(round(pivot_position[1] - pivot_offset[1] * offset_scale)),
                rotated_surface.get_width(),
                rotated_surface.get_height(),
            ),
        )

    def set_group_local_rect(self, group, local_rect):
        """Set group local rect and sync the frame-local group origin."""
        group.set_local_rect(local_rect)
        self.frame.set_group_origin(group.id, group.local_rect.topleft)

    def get_layout_signature(self):
        """Return frame-local inputs that require fan layout recalculation."""
        frame_rect = self.frame.content_rect
        return (
            (frame_rect.x, frame_rect.y, frame_rect.width, frame_rect.height),
            self.get_frame_screen_scale(),
            self.scale_factor,
            self.max_total_angle,
            self.reference_card_count,
            self.radius,
            self.orientation_degrees,
            self.center_offset,
            self.card_count,
            tuple(self.get_card_resource_key(index) for index in range(self.card_count)),
        )

    def get_frame_screen_scale(self):
        if hasattr(self.frame, "get_content_screen_scale"):
            return self.frame.get_content_screen_scale() or 1.0
        return 1.0

    def get_activity_screen_scale(self):
        if self.scale_factor is None:
            return self.get_frame_screen_scale()
        return self.scale_factor

    def get_activity_local_scale(self):
        return self.get_activity_screen_scale() / self.get_frame_screen_scale()

    def scale_surface(self, surface):
        """Вернуть surface с внутренним масштабом веера."""
        if self.scale_factor is None or self.scale_factor == 1.0:
            return surface
        width, height = surface.get_size()
        return pygame.transform.smoothscale(
            surface,
            (
                max(1, int(round(width * self.scale_factor))),
                max(1, int(round(height * self.scale_factor))),
            ),
        )

    @staticmethod
    def calculate_rotated_pivot_offset(scaled_size, rotated_size, angle_degrees):
        """Найти pivot нижнего центра внутри повернутой surface."""
        _, scaled_height = scaled_size
        center = pygame.Vector2(rotated_size[0] / 2, rotated_size[1] / 2)
        bottom_center_from_source_center = pygame.Vector2(0, scaled_height / 2)
        rotated_vector = bottom_center_from_source_center.rotate(angle_degrees)
        pivot = center + rotated_vector
        return int(round(pivot.x)), int(round(pivot.y))

    @staticmethod
    def normalize_pair(value):
        """Return a two-number tuple from fixture/list/tuple input."""
        return normalizers.normalize_float_pair(value)

    @staticmethod
    def normalize_scale_factor(value):
        return normalizers.normalize_scale_factor(value)

    def add_generated_group(self, index):
        """Создать одну visual-only Group рубашки карты."""
        if self.resource_manager is None:
            raise RuntimeError("BotHandActivity requires resource_manager")
        resource_key = self.get_card_resource_key(index)
        if not resource_key:
            raise RuntimeError("BotHandActivity requires resource_key")

        group_id = f"{self.group_id_prefix}.{index}"
        group = Group.create_group(
            group_id,
            ((self.card_layer_name, resource_key),),
            resource_manager=self.resource_manager,
        )
        self.group_base_frames[group.id] = tuple(
            frame.copy()
            for frame in group.get_primary_layer_frames()
        )
        self.generated_groups.append(group)
        self.group_hand_indices[group.id] = index
        self.group_resource_keys[group.id] = resource_key
        self.group_card_ids[group.id] = self.get_card_id(index, resource_key)
        self.frame.place_group_local(group, (0, 0))
        return group

    def get_card_id(self, index, resource_key):
        """Return stable visual-selection ID for a generated card slot."""
        return f"{self.group_id_prefix}.card.{index}:{resource_key}"

    def get_card_selection_context(self, group):
        """Return controller-facing selection data for a visual group."""
        hand_index = self.group_hand_indices.get(group.id)
        if hand_index is None:
            return None
        return {
            "group_id": group.id,
            "hand_index": hand_index,
            "card_id": self.group_card_ids.get(group.id, group.id),
            "resource_key": self.get_card_resource_key(hand_index),
            "frame_id": self.frame.id,
        }

    def get_card_resource_key(self, index):
        """Return the resource key for a generated card slot."""
        if self.card_resource_provider is not None:
            return self.card_resource_provider(index)
        return self.resource_key

    def get_group_card_screen_geometry(self, group):
        """Return screen-space center/size/angle geometry for a generated card."""
        if group not in self.generated_groups:
            raise ValueError(f"Group is not owned by this hand activity: {getattr(group, 'id', group)!r}")
        index = self.group_hand_indices.get(group.id)
        if index is None:
            raise ValueError(f"Group has no hand index: {group.id}")

        count = len(self.generated_groups)
        occupied_angle, angle_step = self.calculate_fan_angles(count)
        local_angle = self.calculate_card_angle(index, count, occupied_angle, angle_step)
        angle = self.orientation_degrees + local_angle
        base_surface = self.group_base_frames[group.id][0]
        scale = group.get_effective_screen_scale() if hasattr(group, "get_effective_screen_scale") else 1.0
        return {
            "center": tuple(group.rect.center),
            "size": (
                max(1, int(round(base_surface.get_width() * scale))),
                max(1, int(round(base_surface.get_height() * scale))),
            ),
            "angle_degrees": float(angle),
        }

    def iter_generated_groups(self):
        """Return generated visual-only groups in draw order."""
        return self.iter_groups_in_draw_order()

    def iter_groups_in_draw_order(self):
        count = len(self.generated_groups)
        return tuple(sorted(self.generated_groups, key=lambda group: self.get_group_draw_slot(group, count)))

    def get_group_draw_slot(self, group, count):
        index = self.group_hand_indices.get(group.id)
        if index is None:
            return 0.0
        return self.calculate_slot_position(index, count)

    def draw(self, screen):
        """Отрисовать generated visual-only Group, которыми владеет Activity."""
        self.draw_debug_overlay(screen)

    def draw_debug_overlay(self, screen):
        if self.debug_fan_rect and debug_overlay.should_draw_activity_rect():
            self.draw_fan_rect(screen)

    def draw_fan_rect(self, screen):
        bounds = self.calculate_fan_rect()
        if bounds is not None:
            pygame.draw.rect(screen, self.debug_fan_rect_color, bounds, 2)

    def calculate_fan_rect(self):
        bounds = None
        for group in self.generated_groups:
            bounds = group.rect.copy() if bounds is None else bounds.union(group.rect)
        return bounds

    def get_fan_occupied_screen_rect(self):
        """Return the current rendered fan bounds for an explicit screen layout consumer."""
        return self.calculate_fan_rect()

    def get_reference_card_surface(self, resource_key=None):
        for group in self.generated_groups:
            frames = self.group_base_frames.get(group.id)
            if frames:
                return frames[0]
        if resource_key is not None and self.resource_manager is not None:
            frames = self.resource_manager.get_frames(resource_key)
            if frames:
                return frames[0]
        if self.resource_manager is not None and self.resource_key is not None:
            frames = self.resource_manager.get_frames(self.resource_key)
            if frames:
                return frames[0]
        raise RuntimeError("Cannot resolve reference card surface for projected bot-hand geometry")

    def clear_generated_groups(self):
        """Удалить все generated visual-only Group из frame и владения."""
        for group in self.generated_groups:
            self.frame.remove_group(group.id)
        self.generated_groups = []
        self.group_hand_indices = {}
        self.group_card_ids = {}
        self.group_resource_keys = {}
        self.group_base_frames = {}
        self._last_layout_signature = None

    def reindex_generated_groups(self):
        """Keep hand indices aligned with the current generated group order."""
        for index, group in enumerate(self.generated_groups):
            self.group_hand_indices[group.id] = index
            resource_key = self.group_resource_keys.get(group.id)
            if resource_key is not None:
                self.group_card_ids[group.id] = self.get_card_id(index, resource_key)

    def remove_generated_group(self, group, relayout=True):
        """Remove one generated visual-only Group from this hand activity."""
        if group not in self.generated_groups:
            return None
        self.generated_groups.remove(group)
        self.frame.remove_group(group.id)
        self.group_hand_indices.pop(group.id, None)
        self.group_card_ids.pop(group.id, None)
        self.group_resource_keys.pop(group.id, None)
        self.group_base_frames.pop(group.id, None)
        self.reindex_generated_groups()
        self.card_count = max(0, self.card_count - 1)
        self._last_layout_signature = None
        if relayout and self.started:
            self.apply_fan_layout()
        return group

    def is_finished(self):
        """Рука бота - долгоживущий режим, сама по времени не завершается."""
        return self._finished

    def finish(self):
        """Завершить режим и удалить generated visual-only Group.

        Жизненный цикл игровых сущностей при этом не меняется.
        """
        self.clear_generated_groups()
        super().finish()
