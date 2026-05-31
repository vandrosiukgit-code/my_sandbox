"""Активная экранная зона.

ActiveZone - это экранный контейнер для GuiActor-ов. Она не знает правил
игры и не решает, почему карта находится в руке или на столе. Она отвечает
только за экранную геометрию: где зона расположена, какие actor ID сейчас
относятся к зоне и как поставить эти actor-ы внутри своего rect.
"""

import pygame

from base import BaseActiveZone


class ActiveZone(BaseActiveZone):
    """Экранная зона, которая размещает actor-ы внутри своего rect."""

    def __init__(self, zone_id, rect, hit_rect=None, actor_ids=None, padding=0, spacing=12):
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
        self.actor_ids = list(actor_ids or [])
        self.padding = padding
        self.spacing = spacing

    @property
    def id(self):
        """Стабильный ID экранной зоны."""
        return self.zone_id

    @property
    def rect(self):
        """Прямоугольник зоны в координатах экрана."""
        return self._rect

    @property
    def hit_rect(self):
        """Область взаимодействия зоны в координатах экрана."""
        return self._hit_rect

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
        x = self.rect.x + self.padding + index * self.get_actor_step(actor)
        y = self.rect.y + self.padding
        return x, y

    def apply_layout(self, actor_store):
        """Поставить actor-ы из actor_store на позиции внутри зоны.

        ActiveZone работает только с ID. Сами GuiActor она получает через
        actor_store, поэтому не становится владельцем графических объектов.
        """
        actor_count = len(self.actor_ids)
        for index, actor_id in enumerate(self.actor_ids):
            actor = actor_store.get(actor_id)
            actor.set_position(*self.calculate_actor_position(index, actor_count, actor))

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
            "rect": tuple(self.rect),
            "hit_rect": tuple(self.hit_rect),
            "actor_ids": tuple(self.actor_ids),
            "padding": self.padding,
            "spacing": self.spacing,
        }
