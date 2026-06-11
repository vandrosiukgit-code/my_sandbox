"""Активная экранная зона.

Frame - это экранный контейнер для Group-ов. Она не знает правил
игры и не решает, почему карта находится в руке или на столе. Она отвечает
только за экранную геометрию: где зона расположена, какие group ID сейчас
относятся к зоне и как поставить эти group-ы внутри своего rect.
"""

import pygame

from base import BaseFrame
from game_screen import debug_overlay
from game_screen.events import FrameHit


class Frame(BaseFrame):
    """Экранная зона, которая размещает group-ы внутри своего rect."""

    def __init__(
        self,
        frame_id,
        rect,
        hit_rect=None,
        group_ids=None,
        padding=0,
        spacing=12,
        parent_frame=None,
        scale_factor=None,
    ):
        """Создать активную экранную зону.

        Args:
            frame_id: Стабильный ID зоны, например "bottom_hand".
            rect: Позиция и размер зоны в координатах parent Frame.
            hit_rect: Область клика/взаимодействия в координатах parent Frame.
                Если не задана, равна rect.
            group_ids: Начальный список group ID внутри зоны.
            padding: Внутренний отступ для базовой раскладки.
            spacing: Расстояние между group-ами в базовой раскладке.
        """
        self.frame_id = frame_id
        self._rect = self.round_rect(rect)
        self._hit_rect = self.round_rect(hit_rect) if hit_rect is not None else self._rect.copy()
        self.parent_frame = parent_frame
        self.child_frames = {}
        self.group_ids = list(group_ids or [])
        self.padding = padding
        self.spacing = spacing
        self.scale_factor = None if scale_factor is None else float(scale_factor)
        self.group_origins = {}
        self.actions = []
        self.hide_rect = True

    @property
    def id(self):
        """Стабильный ID экранной зоны."""
        return self.frame_id

    @property
    def rect(self):
        """Прямоугольник зоны в координатах экрана."""
        return self._to_screen_rect(self._rect)

    @property
    def hit_rect(self):
        """Область взаимодействия зоны в координатах экрана."""
        return self._to_screen_rect(self._hit_rect)

    @property
    def local_rect(self):
        """Rectangle in the parent frame coordinate system."""
        return self._rect.copy()

    @property
    def local_hit_rect(self):
        """Interaction rectangle in the parent frame coordinate system."""
        return self._hit_rect.copy()

    @property
    def content_rect(self):
        """Child coordinate space of this frame, rooted at (0, 0)."""
        return pygame.Rect(0, 0, self._rect.width, self._rect.height)

    def get_parent_screen_scale(self):
        """Return screen scale inherited from the parent frame."""
        if self.parent_frame is None:
            return 1.0
        return self.parent_frame.get_content_screen_scale()

    def get_content_screen_scale(self):
        """Return screen scale for this frame's children."""
        if self.scale_factor is not None:
            return self.scale_factor
        return self.get_parent_screen_scale()

    def add_child_frame(self, frame):
        """Attach a child frame to this frame."""
        if frame.id in self.child_frames:
            raise ValueError(f"Child Frame already exists: {frame.id}")
        frame.parent_frame = self
        self.child_frames[frame.id] = frame
        return frame

    def get_child_frame(self, frame_id):
        """Return a direct child frame by ID."""
        return self.child_frames[frame_id]

    def remove_child_frame(self, frame_id):
        """Detach and return a direct child frame by ID."""
        frame = self.child_frames.pop(frame_id, None)
        if frame is not None:
            frame.parent_frame = None
        return frame

    def has_child_frame(self, frame_id):
        """Return True when this frame directly owns child frame_id."""
        return frame_id in self.child_frames

    def set_local_position(self, x, y):
        """Move this frame inside its parent coordinate system."""
        old_position = self._rect.topleft
        self._rect.topleft = self.round_pair((x, y))
        self._hit_rect.move_ip(
            self._rect.x - old_position[0],
            self._rect.y - old_position[1],
        )

    def set_local_rect(self, rect):
        """Set this frame rect inside its parent coordinate system."""
        self._rect = self.round_rect(rect)
        self._hit_rect = self._rect.copy()

    def set_scale_factor(self, scale_factor):
        """Set local content scale for this frame and its descendants."""
        self.scale_factor = None if scale_factor is None else float(scale_factor)

    def set_group_ids(self, group_ids):
        """Задать полный список group ID в зоне.

        Этот метод удобен, когда GameScreen читает fixture из GameController:
        он берет список card_id из логической зоны и передает его сюда.
        """
        self.group_ids = list(group_ids)

    def add_group_id(self, group_id):
        """Добавить group ID в зону без дублей."""
        if group_id not in self.group_ids:
            self.group_ids.append(group_id)

    def remove_group_id(self, group_id):
        """Убрать group ID из зоны, если он там есть."""
        if group_id in self.group_ids:
            self.group_ids.remove(group_id)
        self.group_origins.pop(group_id, None)

    def calculate_group_position(self, index, group_count, group=None):
        """Рассчитать screen-позицию group-а внутри зоны.

        Сейчас это простая горизонтальная раскладка слева направо. Она нужна
        как безопасная заготовка. Позже здесь можно заменить алгоритм на веер,
        центрирование, стопку колоды или любую другую схему.
        """
        return self.to_screen(self.calculate_group_local_position(index, group_count, group))

    def place_group_local(self, group, local_position):
        """Place a group in this frame using frame-local coordinates."""
        local_position = self.round_pair(local_position)
        self.add_group_id(group.id)
        if hasattr(group, "set_parent_frame"):
            group.set_parent_frame(self)
        if hasattr(group, "set_local_position"):
            group.set_local_position(*local_position)
        else:
            group.set_position(*self.to_screen(local_position))
        self.set_group_origin(group.id, local_position)
        return group

    def move_group_local(self, group, local_position):
        """Move an already placed group using frame-local coordinates."""
        return self.place_group_local(group, local_position)

    def set_group_origin(self, group_id, local_position):
        """Store the latest frame-local layout origin for a group."""
        self.group_origins[group_id] = self.round_pair(local_position)

    def remove_group(self, group_id):
        """Remove group placement and origin metadata from this frame."""
        self.remove_group_id(group_id)
        self.group_origins.pop(group_id, None)

    def calculate_group_local_position(self, index, group_count, group=None):
        """Return group position in the frame local coordinate system."""
        _ = group_count
        x = self.padding + index * self.get_group_step(group)
        y = self.padding
        return x, y

    def apply_layout(self, group_store):
        """Поставить group-ы из group_store на позиции внутри зоны.

        Frame работает только с ID. Сами Group она получает через
        group_store, поэтому не становится владельцем графических объектов.
        """
        group_count = len(self.group_ids)
        for index, group_id in enumerate(self.group_ids):
            group = group_store.get(group_id)
            local_position = self.calculate_group_local_position(index, group_count, group)
            self.place_group_local(group, local_position)

    def add_action(self, action):
        """Add a visual Action owned by this frame."""
        self.cancel_conflicting_actions(action)
        self.actions.append(action)
        if hasattr(action, "start"):
            action.start()
        return action

    def cancel_conflicting_actions(self, next_action):
        """Cancel running actions that target the same group property."""
        next_group_ids = set(getattr(next_action, "group_ids", ()))
        next_properties = set(getattr(next_action, "animated_properties", ()))
        if not next_group_ids or not next_properties:
            return

        kept_actions = []
        for action in self.actions:
            group_conflict = next_group_ids.intersection(getattr(action, "group_ids", ()))
            property_conflict = next_properties.intersection(getattr(action, "animated_properties", ()))
            if group_conflict and property_conflict:
                if hasattr(action, "cancel"):
                    action.cancel()
            else:
                kept_actions.append(action)
        self.actions = kept_actions

    def update_actions(self, dt):
        """Update active visual Actions and drop finished ones."""
        for frame in self.child_frames.values():
            frame.update_actions(dt)

        running_actions = []
        for action in self.actions:
            action.update(dt)
            if not self.is_action_finished(action):
                running_actions.append(action)
        self.actions = running_actions

    @staticmethod
    def is_action_finished(action):
        is_finished = getattr(action, "is_finished", False)
        if callable(is_finished):
            return is_finished()
        return bool(is_finished)

    def to_local(self, screen_pos):
        """Convert screen coordinates to this frame local coordinates."""
        origin = self.get_screen_origin()
        scale = self.get_content_screen_scale()
        if scale == 0:
            return (0, 0)
        return (
            self.round_coord((screen_pos[0] - origin[0]) / scale),
            self.round_coord((screen_pos[1] - origin[1]) / scale),
        )

    def to_screen(self, local_pos):
        """Convert local frame coordinates to screen coordinates."""
        origin = self.get_screen_origin()
        scale = self.get_content_screen_scale()
        return (
            self.round_coord(origin[0] + local_pos[0] * scale),
            self.round_coord(origin[1] + local_pos[1] * scale),
        )

    def get_screen_origin(self):
        """Return this frame content origin in screen coordinates."""
        if self.parent_frame is None:
            return self.round_pair(self._rect.topleft)
        return self.parent_frame.to_screen(self._rect.topleft)

    def hit_test(self, screen_pos, group_store):
        """Return FrameHit for the topmost group under screen_pos inside this frame."""
        if not self.contains_point(screen_pos):
            return None

        local_pos = self.to_local(screen_pos)
        for frame in reversed(tuple(self.child_frames.values())):
            hit = frame.hit_test(screen_pos, group_store)
            if hit is not None:
                return hit

        for group_id in reversed(self.group_ids):
            if hasattr(group_store, "has") and not group_store.has(group_id):
                continue
            group = group_store.get(group_id)
            if group.hit_rect.collidepoint(screen_pos):
                return FrameHit(
                    frame_id=self.id,
                    group_id=group_id,
                    screen_pos=tuple(screen_pos),
                    local_pos=local_pos,
                )

        return FrameHit(
            frame_id=self.id,
            group_id=None,
            screen_pos=tuple(screen_pos),
            local_pos=local_pos,
        )

    def get_group_origin(self, group_id):
        """Вернуть последнюю рассчитанную локальную точку group-а."""
        return self.group_origins.get(group_id, self.content_rect.topleft)

    def contains_point(self, point):
        """Проверить попадание точки в hit_rect зоны."""
        return self.hit_rect.collidepoint(point)

    def get_group_step(self, group):
        """Вернуть шаг между group-ами для базовой раскладки.

        Если group уже имеет rect, шаг равен его ширине плюс spacing. Если
        group не передан, используется только spacing. Это позволяет методу
        работать и в ранних черновых сценариях.
        """
        if group is None:
            return self.spacing
        if hasattr(group, "get_scaled_local_rect"):
            return group.get_scaled_local_rect().width + self.spacing
        return group.local_rect.width + self.spacing

    def to_payload(self):
        """Вернуть словарь с параметрами зоны для отладки и документации."""
        return {
            "frame_id": self.id,
            "parent_frame_id": self.parent_frame.id if self.parent_frame is not None else None,
            "local_rect": tuple(self.local_rect),
            "rect": tuple(self.rect),
            "hit_rect": tuple(self.hit_rect),
            "group_ids": tuple(self.group_ids),
            "child_frame_ids": tuple(self.child_frames),
            "group_origins": dict(self.group_origins),
            "action_count": len(self.actions),
            "padding": self.padding,
            "spacing": self.spacing,
            "scale_factor": self.scale_factor,
            "content_screen_scale": self.get_content_screen_scale(),
        }

    def draw_debug_rects(self, screen, depth=0):
        pygame.draw.rect(screen, debug_overlay.get_rect_color(depth), self.rect, 2)

    def draw_debug_tree(self, screen, depth=0):
        if self.should_draw_debug_rects(depth):
            self.draw_debug_rects(screen, depth)
        for child_frame in self.child_frames.values():
            child_frame.draw_debug_tree(screen, depth + 1)

    def set_rect_visibility(self, hide_rect=True):
        """Set whether this Frame hides its debug rect overlay."""
        self.hide_rect = bool(hide_rect)
        return self

    def should_draw_debug_rects(self, depth=0):
        """Return True when this Frame should draw debug rects."""
        return debug_overlay.should_draw_frame_rect(self, depth)

    def _to_screen_rect(self, rect):
        """Convert a rect from parent-frame coordinates to screen coordinates."""
        parent_scale = self.get_parent_screen_scale()
        content_scale = self.get_content_screen_scale()
        origin = self.get_screen_origin()
        screen_pos = (
            self.round_coord(origin[0] + (rect.x - self._rect.x) * parent_scale),
            self.round_coord(origin[1] + (rect.y - self._rect.y) * parent_scale),
        )
        screen_size = (
            max(0, self.round_coord(rect.width * content_scale)),
            max(0, self.round_coord(rect.height * content_scale)),
        )
        return pygame.Rect(screen_pos, screen_size)

    @staticmethod
    def round_coord(value):
        """Round one coordinate/size value to a real screen pixel."""
        return int(round(float(value)))

    @classmethod
    def round_pair(cls, values):
        return cls.round_coord(values[0]), cls.round_coord(values[1])

    @classmethod
    def round_rect(cls, rect):
        if isinstance(rect, pygame.Rect):
            values = rect.x, rect.y, rect.width, rect.height
        else:
            values = tuple(rect)
        return pygame.Rect(
            cls.round_coord(values[0]),
            cls.round_coord(values[1]),
            cls.round_coord(values[2]),
            cls.round_coord(values[3]),
        )
