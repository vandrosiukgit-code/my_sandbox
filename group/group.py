"""Пассивный GUI group проекта The Fool's Reef.

Group - это простой визуальный кирпичик. Он не знает правил игры, не
загружает PNG сам и не содержит локальной раскладки слоев. Все его слои
рисуются из одной базовой точки group.rect.topleft.
"""

from dataclasses import dataclass

import pygame

from base import BaseGroup
from game_screen import debug_overlay


@dataclass
class Layer:
    """Один графический слой Group.

    Слой хранит только имя, список кадров и индекс текущего кадра. У слоя
    сознательно нет offset, visible и alpha: это архитектурное ограничение,
    чтобы group не превращался в мини-сцену.
    """

    name: str
    frames: list
    position: tuple[int, int] = (0, 0)
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


@dataclass(frozen=True)
class TextStyle:
    """Visual text settings used to render text into a Layer surface."""

    font_name: str | None = None
    font_size: int = 24
    color: tuple[int, int, int] = (255, 255, 255)
    antialias: bool = True


def create_text_layer(layer_name, text, size=None, style=None, position=(0, 0)):
    """Create a normal Layer whose frame is a rendered text surface."""
    return Layer(
        name=layer_name,
        frames=[render_text_surface(text, style or TextStyle(), size)],
        position=position,
    )


def render_text_surface(text, style, size=None):
    """Render text into a pygame.Surface, optionally centered in a fixed size."""
    if not pygame.font.get_init():
        pygame.font.init()

    font = get_text_font(style)
    text_surface = font.render(str(text), style.antialias, style.color)
    if size is None:
        return text_surface

    surface = pygame.Surface(size, pygame.SRCALPHA)
    surface.blit(text_surface, text_surface.get_rect(center=surface.get_rect().center))
    return surface


def get_text_font(style):
    """Return a pygame Font from a TextStyle."""
    if style.font_name:
        return pygame.font.SysFont(style.font_name, style.font_size)
    return pygame.font.Font(None, style.font_size)


class Group(BaseGroup):
    """Пассивный drawable-объект с rect, hit_rect, scale_factor и слоями кадров.

    Group не различает статику и анимацию. Любой PNG после ResourceManager
    становится списком кадров: обычная картинка - это список из одного кадра,
    spritesheet - список из нескольких кадров. Activity может менять текущий
    кадр слоя, позицию group-а и scale_factor, но не правила игры.
    """

    def __init__(self, group_id, rect=(0, 0, 0, 0), layers=None, scale_factor=1.0):
        """Создать Group из готовых списков кадров.

        Args:
            group_id: Стабильный ID, общий для визуального слоя и логики.
            rect: Базовый прямоугольник group-а на экране.
            layers: Слои в порядке отрисовки.
            scale_factor: Масштаб всего group-а. Масштабируются rect, hit_rect и
                все кадры при отрисовке, но исходные Surface не меняются.
        """
        if not group_id:
            raise ValueError("Group требует непустой group_id")

        self.group_id = group_id
        self._base_rect = pygame.Rect(rect)
        self._rect = self._base_rect.copy()
        self._base_hit_rect = self._base_rect.copy()
        self._hit_rect = self._base_hit_rect.copy()
        self.scale_factor = float(scale_factor)
        self.hide_rect = True
        self.rect_debug_layer_ids = None
        self.layers = []

        for layer in layers or []:
            self.add_layer(layer)

        if self._base_rect.size == (0, 0):
            self.refresh_rect_from_layers()
        self.apply_scale()

    @classmethod
    def create_group(cls, group_id, graphics, rect=(0, 0, 0, 0), resource_manager=None):
        """Собрать Group по описанию слоев и ключам ResourceManager.

        Это удобная точка сборки, а не отдельная фабрика. Каждый элемент graphics
        задает слой в порядке отрисовки:

        - ("layer_name", "resource.key")
        - ("layer_name", "resource.key", (x, y))
        - {"name": "layer_name", "resource_key": "resource.key", "position": (x, y)}

        ResourceManager передается снаружи и всегда отдает список кадров через
        get_frames(). Так Group не импортирует ресурсный слой напрямую.
        """
        if resource_manager is None:
            raise ValueError("Group.create_group() требует resource_manager с методом get_frames()")

        layers = []
        for graphic in graphics:
            layer_name, resource_key, position = cls.normalize_graphic(graphic)
            layers.append(Layer(layer_name, resource_manager.get_frames(resource_key), position))
        return cls(group_id=group_id, rect=rect, layers=layers)

    @staticmethod
    def normalize_graphic(graphic):
        """Привести описание слоя к layer_name/resource_key/position."""
        if isinstance(graphic, dict):
            layer_name = graphic.get("name") or graphic.get("layer_name")
            resource_key = graphic.get("resource_key")
            position = graphic.get("position", graphic.get("local_position", (0, 0)))
            if not layer_name or not resource_key:
                raise ValueError(f"У слоя должен быть name и resource_key: {graphic!r}")
            return layer_name, resource_key, Group.normalize_layer_position(position)

        if isinstance(graphic, (tuple, list)) and len(graphic) >= 2:
            position = graphic[2] if len(graphic) >= 3 else (0, 0)
            return graphic[0], graphic[1], Group.normalize_layer_position(position)

        raise TypeError(
            "Слой должен быть описан как (layer_name, resource_key) "
            "или (layer_name, resource_key, (x, y)) "
            "или {'name': ..., 'resource_key': ..., 'position': ...}"
        )

    @staticmethod
    def normalize_layer_position(position):
        if position is None:
            return (0, 0)
        if isinstance(position, dict):
            return (int(position.get("x", 0)), int(position.get("y", 0)))
        if isinstance(position, (tuple, list)) and len(position) >= 2:
            return (int(position[0]), int(position[1]))
        raise TypeError(f"Позиция слоя должна быть (x, y): {position!r}")

    @property
    def id(self):
        """Стабильный ID group-а."""
        return self.group_id

    @property
    def rect(self):
        """Текущий прямоугольник group-а на экране с учетом scale_factor."""
        return self._rect

    @property
    def hit_rect(self):
        """Обязательная область взаимодействия group-а с учетом scale_factor."""
        return self._hit_rect

    def update(self, dt):
        """Обновить group.

        Метод намеренно пустой: Group не проигрывает анимацию сам. Временную
        смену кадров, перемещение и масштабирование выполняют Activity или экран.
        """
        _ = dt

    def draw(self, screen):
        """Отрисовать текущий кадр каждого слоя в базовой точке group.rect.topleft."""
        for layer in self.layers:
            surface = layer.get_current_frame()
            if surface is None:
                continue
            screen.blit(self.get_scaled_surface(surface), self.get_layer_screen_position(layer))
        if self.should_draw_debug_rects():
            self.draw_debug_rects(screen)

    def set_rect_visibility(self, hide_rect=True, layer_ids=None):
        """Set whether this Group hides its debug rect overlay."""
        self.hide_rect = bool(hide_rect)
        self.rect_debug_layer_ids = self.normalize_rect_debug_layer_ids(layer_ids)
        return self

    def should_draw_debug_rects(self):
        """Return True when this Group should draw debug rects."""
        return debug_overlay.DEBUG_RECTS or not self.hide_rect

    @staticmethod
    def normalize_rect_debug_layer_ids(layer_ids):
        if layer_ids is None:
            return None
        if isinstance(layer_ids, str):
            return frozenset((layer_ids,))
        return frozenset(layer_ids)

    def set_position(self, x, y):
        """Переместить group на экране без изменения его базового размера."""
        old_position = self._base_rect.topleft
        self._base_rect.topleft = (int(x), int(y))
        self._base_hit_rect.move_ip(
            self._base_rect.x - old_position[0],
            self._base_rect.y - old_position[1],
        )
        self.apply_scale()

    def set_rect(self, rect):
        """Задать базовый rect group-а и синхронизировать hit_rect."""
        self._base_rect = pygame.Rect(rect)
        self._base_hit_rect = self._base_rect.copy()
        self.apply_scale()

    def set_hit_rect(self, rect):
        """Задать базовую область клика group-а.

        hit_rect может отличаться от rect, но остается геометрией всего group-а,
        а не отдельного слоя.
        """
        self._base_hit_rect = pygame.Rect(rect)
        self.apply_scale()

    def set_scale_factor(self, scale_factor):
        """Задать масштаб всего group-а от исходного базового rect."""
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
                position=self.normalize_layer_position(layer.get("position", (0, 0))),
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
        """Выставить размер group-а по первому доступному кадру.

        Это вспомогательный режим для ранних прототипов. В зрелом коде экран или
        сборка group-а обычно задают rect явно.
        """
        for layer in self.layers:
            surface = layer.get_current_frame()
            if surface is not None:
                layer_x, layer_y = layer.position
                surface_width, surface_height = surface.get_size()
                self._base_rect.size = (
                    max(self._base_rect.width, layer_x + surface_width),
                    max(self._base_rect.height, layer_y + surface_height),
                )
                self._base_hit_rect = self._base_rect.copy()


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

    def get_layer_screen_position(self, layer):
        return (
            self._rect.x + round(layer.position[0] * self.scale_factor),
            self._rect.y + round(layer.position[1] * self.scale_factor),
        )

    def get_layer_rect(self, layer):
        surface = layer.get_current_frame()
        if surface is None:
            return pygame.Rect(self.get_layer_screen_position(layer), (0, 0))
        scaled_surface = self.get_scaled_surface(surface)
        return pygame.Rect(self.get_layer_screen_position(layer), scaled_surface.get_size())

    def draw_debug_rects(self, screen, depth=0):
        pygame.draw.rect(screen, debug_overlay.get_rect_color(depth), self.rect, 2)
        for layer in self.iter_debug_layers():
            pygame.draw.rect(screen, debug_overlay.get_rect_color(depth + 1), self.get_layer_rect(layer), 1)

    def iter_debug_layers(self):
        if self.rect_debug_layer_ids is None:
            yield from self.layers
            return

        for layer in self.layers:
            if layer.name in self.rect_debug_layer_ids:
                yield layer

    @staticmethod
    def scale_rect(rect, scale_factor):
        """Масштабировать прямоугольник от его базовой левой верхней точки."""
        return pygame.Rect(
            rect.x,
            rect.y,
            max(0, round(rect.width * scale_factor)),
            max(0, round(rect.height * scale_factor)),
        )
