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
        self._rect = pygame.Rect(rect)
        self._hit_rect = pygame.Rect(hit_rect) if hit_rect is not None else self._rect.copy()
        self.parent_frame = parent_frame
        self.child_frames = {}
        self.group_ids = list(group_ids or [])
        self.padding = padding
        self.spacing = spacing
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

    def set_local_position(self, x, y):
        """Move this frame inside its parent coordinate system."""
        old_position = self._rect.topleft
        self._rect.topleft = (int(x), int(y))
        self._hit_rect.move_ip(
            self._rect.x - old_position[0],
            self._rect.y - old_position[1],
        )

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

    def calculate_group_position(self, index, group_count, group=None):
        """Рассчитать screen-позицию group-а внутри зоны.

        Сейчас это простая горизонтальная раскладка слева направо. Она нужна
        как безопасная заготовка. Позже здесь можно заменить алгоритм на веер,
        центрирование, стопку колоды или любую другую схему.
        """
        return self.to_screen(self.calculate_group_local_position(index, group_count, group))

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
            if hasattr(group, "set_parent_frame"):
                group.set_parent_frame(self)
            if hasattr(group, "set_local_position"):
                group.set_local_position(*local_position)
            else:
                group.set_position(*self.to_screen(local_position))
            self.group_origins[group_id] = local_position

    def add_action(self, action):
        """Add a visual Action owned by this frame."""
        self.actions.append(action)
        if hasattr(action, "start"):
            action.start()
        return action

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
        rect = self.rect
        return (int(screen_pos[0] - rect.x), int(screen_pos[1] - rect.y))

    def to_screen(self, local_pos):
        """Convert local frame coordinates to screen coordinates."""
        if self.parent_frame is None:
            return (int(self._rect.x + local_pos[0]), int(self._rect.y + local_pos[1]))

        parent_local_pos = (
            self._rect.x + local_pos[0],
            self._rect.y + local_pos[1],
        )
        return self.parent_frame.to_screen(parent_local_pos)

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
        return group.rect.width + self.spacing

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
        }

    def draw_debug_rects(self, screen, depth=0):
        pygame.draw.rect(screen, debug_overlay.get_rect_color(depth), self.rect, 2)

    def draw_debug_tree(self, screen, depth=0):
        if self.should_draw_debug_rects():
            self.draw_debug_rects(screen, depth)
        for child_frame in self.child_frames.values():
            child_frame.draw_debug_tree(screen, depth + 1)

    def set_rect_visibility(self, hide_rect=True):
        """Set whether this Frame hides its debug rect overlay."""
        self.hide_rect = bool(hide_rect)
        return self

    def should_draw_debug_rects(self):
        """Return True when this Frame should draw debug rects."""
        return debug_overlay.DEBUG_RECTS or not self.hide_rect

    def _to_screen_rect(self, rect):
        """Convert a rect from parent-frame coordinates to screen coordinates."""
        screen_pos = self.to_screen((rect.x - self._rect.x, rect.y - self._rect.y))
        return pygame.Rect(screen_pos, rect.size)
