"""Активная экранная зона.

ActiveZone - это экранный контейнер для GuiActor-ов. Она не знает правил
игры и не решает, почему карта находится в руке или на столе. Она отвечает
только за экранную геометрию: где зона расположена, какие actor ID сейчас
относятся к зоне и как поставить эти actor-ы внутри своего rect.
"""

import pygame

from base import BaseActiveZone
from game_screen.events import ZoneHit


class ActiveZone(BaseActiveZone):
    """Экранная зона, которая размещает actor-ы внутри своего rect."""

    def __init__(
        self,
        zone_id,
        rect,
        hit_rect=None,
        actor_ids=None,
        padding=0,
        spacing=12,
        parent_zone=None,
    ):
        """Создать активную экранную зону.

        Args:
            zone_id: Стабильный ID зоны, например "bottom_hand".
            rect: Позиция и размер зоны в координатах экрана.
            hit_rect: Область клика/взаимодействия. Если не задана, равна rect.
            actor_ids: Начальный список actor ID внутри зоны.
            padding: Внутренний отступ для базовой раскладки.
            spacing: Расстояние между actor-ами в базовой раскладке.
        """
        self.zone_id = zone_id
        self._rect = pygame.Rect(rect)
        self._hit_rect = pygame.Rect(hit_rect) if hit_rect is not None else self._rect.copy()
        self.parent_zone = parent_zone
        self.child_zones = {}
        self.actor_ids = list(actor_ids or [])
        self.padding = padding
        self.spacing = spacing
        self.actor_origins = {}
        self.actions = []

    @property
    def id(self):
        """Стабильный ID экранной зоны."""
        return self.zone_id

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
        """Rectangle in the parent zone coordinate system."""
        return self._rect

    def add_child_zone(self, zone):
        """Attach a child zone to this zone."""
        if zone.id in self.child_zones:
            raise ValueError(f"Child ActiveZone already exists: {zone.id}")
        zone.parent_zone = self
        self.child_zones[zone.id] = zone
        return zone

    def get_child_zone(self, zone_id):
        """Return a direct child zone by ID."""
        return self.child_zones[zone_id]

    def set_local_position(self, x, y):
        """Move this zone inside its parent coordinate system."""
        old_position = self._rect.topleft
        self._rect.topleft = (int(x), int(y))
        self._hit_rect.move_ip(
            self._rect.x - old_position[0],
            self._rect.y - old_position[1],
        )

    def set_actor_ids(self, actor_ids):
        """Задать полный список actor ID в зоне.

        Этот метод удобен, когда GameScreen читает fixture из GameController:
        он берет список card_id из логической зоны и передает его сюда.
        """
        self.actor_ids = list(actor_ids)

    def add_actor_id(self, actor_id):
        """Добавить actor ID в зону без дублей."""
        if actor_id not in self.actor_ids:
            self.actor_ids.append(actor_id)

    def remove_actor_id(self, actor_id):
        """Убрать actor ID из зоны, если он там есть."""
        if actor_id in self.actor_ids:
            self.actor_ids.remove(actor_id)

    def calculate_actor_position(self, index, actor_count, actor=None):
        """Рассчитать позицию actor-а внутри зоны.

        Сейчас это простая горизонтальная раскладка слева направо. Она нужна
        как безопасная заготовка. Позже здесь можно заменить алгоритм на веер,
        центрирование, стопку колоды или любую другую схему.
        """
        return self.to_screen(self.calculate_actor_local_position(index, actor_count, actor))

    def calculate_actor_local_position(self, index, actor_count, actor=None):
        """Return actor position in the zone local coordinate system."""
        _ = actor_count
        x = self.padding + index * self.get_actor_step(actor)
        y = self.padding
        return x, y

    def apply_layout(self, actor_store):
        """Поставить actor-ы из actor_store на позиции внутри зоны.

        ActiveZone работает только с ID. Сами GuiActor она получает через
        actor_store, поэтому не становится владельцем графических объектов.
        """
        actor_count = len(self.actor_ids)
        for index, actor_id in enumerate(self.actor_ids):
            actor = actor_store.get(actor_id)
            position = self.calculate_actor_position(index, actor_count, actor)
            actor.set_position(*position)
            self.actor_origins[actor_id] = position

    def add_action(self, action):
        """Add a visual Action owned by this zone."""
        self.actions.append(action)
        if hasattr(action, "start"):
            action.start()
        return action

    def update_actions(self, dt):
        """Update active visual Actions and drop finished ones."""
        for zone in self.child_zones.values():
            zone.update_actions(dt)

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
        """Convert screen coordinates to this zone local coordinates."""
        rect = self.rect
        return (int(screen_pos[0] - rect.x), int(screen_pos[1] - rect.y))

    def to_screen(self, local_pos):
        """Convert local zone coordinates to screen coordinates."""
        if self.parent_zone is None:
            return (int(self._rect.x + local_pos[0]), int(self._rect.y + local_pos[1]))

        parent_local_pos = (
            self._rect.x + local_pos[0],
            self._rect.y + local_pos[1],
        )
        return self.parent_zone.to_screen(parent_local_pos)

    def hit_test(self, screen_pos, actor_store):
        """Return ZoneHit for the topmost actor under screen_pos inside this zone."""
        if not self.contains_point(screen_pos):
            return None

        local_pos = self.to_local(screen_pos)
        for zone in reversed(tuple(self.child_zones.values())):
            hit = zone.hit_test(screen_pos, actor_store)
            if hit is not None:
                return hit

        for actor_id in reversed(self.actor_ids):
            actor = actor_store.get(actor_id)
            if actor.hit_rect.collidepoint(screen_pos):
                return ZoneHit(
                    zone_id=self.id,
                    actor_id=actor_id,
                    screen_pos=tuple(screen_pos),
                    local_pos=local_pos,
                )

        return ZoneHit(
            zone_id=self.id,
            actor_id=None,
            screen_pos=tuple(screen_pos),
            local_pos=local_pos,
        )

    def get_actor_origin(self, actor_id):
        """Вернуть последнюю рассчитанную экранную точку actor-а."""
        return self.actor_origins.get(actor_id, self.rect.topleft)

    def contains_point(self, point):
        """Проверить попадание точки в hit_rect зоны."""
        return self.hit_rect.collidepoint(point)

    def get_actor_step(self, actor):
        """Вернуть шаг между actor-ами для базовой раскладки.

        Если actor уже имеет rect, шаг равен его ширине плюс spacing. Если
        actor не передан, используется только spacing. Это позволяет методу
        работать и в ранних черновых сценариях.
        """
        if actor is None:
            return self.spacing
        return actor.rect.width + self.spacing

    def to_payload(self):
        """Вернуть словарь с параметрами зоны для отладки и документации."""
        return {
            "zone_id": self.id,
            "parent_zone_id": self.parent_zone.id if self.parent_zone is not None else None,
            "local_rect": tuple(self.local_rect),
            "rect": tuple(self.rect),
            "hit_rect": tuple(self.hit_rect),
            "actor_ids": tuple(self.actor_ids),
            "child_zone_ids": tuple(self.child_zones),
            "actor_origins": dict(self.actor_origins),
            "action_count": len(self.actions),
            "padding": self.padding,
            "spacing": self.spacing,
        }

    def _to_screen_rect(self, rect):
        """Convert a rect from parent-zone coordinates to screen coordinates."""
        screen_pos = self.to_screen((rect.x - self._rect.x, rect.y - self._rect.y))
        return pygame.Rect(screen_pos, rect.size)
