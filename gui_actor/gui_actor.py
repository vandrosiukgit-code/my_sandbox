"""Пассивный GUI actor проекта The Fool's Reef.

GuiActor - это простой визуальный кирпичик. Он не знает правил игры, не
загружает PNG сам и не содержит локальной раскладки слоев. Все его слои
рисуются из одной базовой точки actor.rect.topleft.
"""

from dataclasses import dataclass

import pygame

from base import BaseGuiActor


@dataclass
class Layer:
    """Один графический слой GuiActor.

    Слой хранит только имя, список кадров и индекс текущего кадра. У слоя
    сознательно нет offset, visible и alpha: это архитектурное ограничение,
    чтобы actor не превращался в мини-сцену.
    """

    name: str
    frames: list
    current_frame_index: int = 0

    def get_current_frame(self):
        """Вернуть текущий pygame.Surface слоя."""
        if not self.frames:
            return None
        return self.frames[self.current_frame_index]

    def set_frame(self, frame_index):
        """Выбрать текущий кадр слоя с защитой от выхода за границы."""
        if not self.frames:
            self.current_frame_index = 0
            return
        self.current_frame_index = max(0, min(int(frame_index), len(self.frames) - 1))


class GuiActor(BaseGuiActor):
    """Пассивный drawable-объект с rect, hit_rect, scale_factor и слоями кадров.

    GuiActor не различает статику и анимацию. Любой PNG после ResourceManager
    становится списком кадров: обычная картинка - это список из одного кадра,
    spritesheet - список из нескольких кадров. Activity может менять текущий
    кадр слоя, позицию actor-а и scale_factor, но не правила игры.
    """

    def __init__(self, actor_id, rect=(0, 0, 0, 0), layers=None, scale_factor=1.0):
        """Создать GuiActor из готовых списков кадров.

        Args:
            actor_id: Стабильный ID, общий для визуального слоя и логики.
            rect: Базовый прямоугольник actor-а на экране.
            layers: Слои в порядке отрисовки.
            scale_factor: Масштаб всего actor-а. Масштабируются rect, hit_rect и
                все кадры при отрисовке, но исходные Surface не меняются.
        """
        if not actor_id:
            raise ValueError("GuiActor требует непустой actor_id")

        self.actor_id = actor_id
        self._base_rect = pygame.Rect(rect)
        self._rect = self._base_rect.copy()
        self._base_hit_rect = self._base_rect.copy()
        self._hit_rect = self._base_hit_rect.copy()
        self.scale_factor = float(scale_factor)
        self.layers = []

        for layer in layers or []:
            self.add_layer(layer)

        if self._base_rect.size == (0, 0):
            self.refresh_rect_from_layers()
        self.apply_scale()

    @classmethod
    def create_actor(cls, actor_id, graphics, rect=(0, 0, 0, 0), resource_manager=None):
        """Собрать GuiActor по описанию слоев и ключам ResourceManager.

        Это удобная точка сборки, а не отдельная фабрика. Каждый элемент graphics
        задает слой в порядке отрисовки:

        - ("layer_name", "resource.key")
        - {"name": "layer_name", "resource_key": "resource.key"}

        ResourceManager передается снаружи и всегда отдает список кадров через
        get_frames(). Так GuiActor не импортирует ресурсный слой напрямую.
        """
        if resource_manager is None:
            raise ValueError("GuiActor.create_actor() требует resource_manager с методом get_frames()")

        layers = []
        for graphic in graphics:
            layer_name, resource_key = cls.normalize_graphic(graphic)
            layers.append(Layer(layer_name, resource_manager.get_frames(resource_key)))
        return cls(actor_id=actor_id, rect=rect, layers=layers)

    @staticmethod
    def normalize_graphic(graphic):
        """Привести описание слоя к паре layer_name/resource_key."""
        if isinstance(graphic, dict):
            layer_name = graphic.get("name") or graphic.get("layer_name")
            resource_key = graphic.get("resource_key")
            if not layer_name or not resource_key:
                raise ValueError(f"У слоя должен быть name и resource_key: {graphic!r}")
            return layer_name, resource_key

        if isinstance(graphic, (tuple, list)) and len(graphic) >= 2:
            return graphic[0], graphic[1]

        raise TypeError(
            "Слой должен быть описан как (layer_name, resource_key) "
            "или {'name': ..., 'resource_key': ...}"
        )

    @property
    def id(self):
        """Стабильный ID actor-а."""
        return self.actor_id

    @property
    def rect(self):
        """Текущий прямоугольник actor-а на экране с учетом scale_factor."""
        return self._rect

    @property
    def hit_rect(self):
        """Обязательная область взаимодействия actor-а с учетом scale_factor."""
        return self._hit_rect

    def update(self, dt):
        """Обновить actor.

        Метод намеренно пустой: GuiActor не проигрывает анимацию сам. Временную
        смену кадров, перемещение и масштабирование выполняют Activity или экран.
        """
        _ = dt

    def draw(self, screen):
        """Отрисовать текущий кадр каждого слоя в базовой точке actor.rect.topleft."""
        for layer in self.layers:
            surface = layer.get_current_frame()
            if surface is None:
                continue
            screen.blit(self.get_scaled_surface(surface), self._rect.topleft)

    def set_position(self, x, y):
        """Переместить actor на экране без изменения его базового размера."""
        old_position = self._base_rect.topleft
        self._base_rect.topleft = (int(x), int(y))
        self._base_hit_rect.move_ip(
            self._base_rect.x - old_position[0],
            self._base_rect.y - old_position[1],
        )
        self.apply_scale()

    def set_rect(self, rect):
        """Задать базовый rect actor-а и синхронизировать hit_rect."""
        self._base_rect = pygame.Rect(rect)
        self._base_hit_rect = self._base_rect.copy()
        self.apply_scale()

    def set_hit_rect(self, rect):
        """Задать базовую область клика actor-а.

        hit_rect может отличаться от rect, но остается геометрией всего actor-а,
        а не отдельного слоя.
        """
        self._base_hit_rect = pygame.Rect(rect)
        self.apply_scale()

    def set_scale_factor(self, scale_factor):
        """Задать масштаб всего actor-а от исходного базового rect."""
        self.scale_factor = float(scale_factor)
        self.apply_scale()

    def add_layer(self, layer):
        """Добавить слой в конец порядка отрисовки."""
        if isinstance(layer, Layer):
            self.layers.append(layer)
            return layer

        if isinstance(layer, dict):
            new_layer = Layer(
                name=layer["name"],
                frames=list(layer.get("frames", [])),
                current_frame_index=layer.get("current_frame_index", 0),
            )
            self.layers.append(new_layer)
            return new_layer

        raise TypeError(f"Неподдерживаемый тип слоя: {type(layer)!r}")

    def set_layer_frame(self, layer_name, frame_index):
        """Установить текущий кадр слоя."""
        self.get_layer(layer_name).set_frame(frame_index)

    def set_layer_frames(self, layer_name, frames):
        """Заменить список кадров слоя."""
        layer = self.get_layer(layer_name)
        layer.frames = list(frames)
        layer.set_frame(0)
        if self._base_rect.size == (0, 0):
            self.refresh_rect_from_layers()
            self.apply_scale()

    def get_layer(self, layer_name):
        """Найти слой по имени."""
        for layer in self.layers:
            if layer.name == layer_name:
                return layer
        raise ValueError(f"Неизвестный слой: {layer_name}")

    def refresh_rect_from_layers(self):
        """Выставить размер actor-а по первому доступному кадру.

        Это вспомогательный режим для ранних прототипов. В зрелом коде экран или
        сборка actor-а обычно задают rect явно.
        """
        for layer in self.layers:
            surface = layer.get_current_frame()
            if surface is not None:
                self._base_rect.size = surface.get_size()
                self._base_hit_rect = self._base_rect.copy()
                return

    def apply_scale(self):
        """Пересчитать rect и hit_rect от базовой геометрии и scale_factor."""
        self._rect = self.scale_rect(self._base_rect, self.scale_factor)
        self._hit_rect = self.scale_rect(self._base_hit_rect, self.scale_factor)

    def get_scaled_surface(self, surface):
        """Вернуть surface, масштабированный текущим scale_factor."""
        if self.scale_factor == 1.0:
            return surface
        width, height = surface.get_size()
        scaled_size = (
            max(1, round(width * self.scale_factor)),
            max(1, round(height * self.scale_factor)),
        )
        return pygame.transform.smoothscale(surface, scaled_size)

    @staticmethod
    def scale_rect(rect, scale_factor):
        """Масштабировать прямоугольник от его базовой левой верхней точки."""
        return pygame.Rect(
            rect.x,
            rect.y,
            max(0, round(rect.width * scale_factor)),
            max(0, round(rect.height * scale_factor)),
        )
