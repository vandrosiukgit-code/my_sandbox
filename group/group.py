"""Пассивный GUI group проекта The Fool's Reef.

Group - это простой визуальный кирпичик. Он не знает правил игры, не
загружает PNG сам и не содержит локальной раскладки слоев. Все его слои
рисуются из одной базовой точки group.rect.topleft.
"""

from dataclasses import dataclass
import os

import pygame

from base import BaseGroup
from game_screen import debug_overlay
import group_config


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
    layer_type: str = "surface"
    resource_key: str | None = None
    text_key: str | None = None
    default_text: str | None = None
    size: tuple[int, int] | None = None
    scale_percent: tuple[int, int] | None = None
    fit_mode: str | None = None
    style: object | None = None

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

    def to_manifest_entry(self):
        """Return serializable layer metadata for GuiManifest."""
        payload = {
            "id": self.name,
            "type": self.layer_type,
            "position": list(self.position),
            "current_frame_index": self.current_frame_index,
            "frame_count": len(self.frames),
        }
        if self.resource_key is not None:
            payload["resource_key"] = self.resource_key
        if self.text_key is not None:
            payload["text_key"] = self.text_key
        if self.default_text is not None:
            payload["default_text"] = self.default_text
        if self.size is not None:
            payload["size"] = list(self.size)
            payload["rect"] = [
                int(self.position[0]),
                int(self.position[1]),
                int(self.size[0]),
                int(self.size[1]),
            ]
        if self.fit_mode is not None:
            payload["fit_mode"] = self.fit_mode
        if self.scale_percent is not None:
            payload["scale_percent"] = list(self.scale_percent)
        if self.style is not None and hasattr(self.style, "to_manifest_entry"):
            payload["style"] = self.style.to_manifest_entry()
        return payload


@dataclass(frozen=True)
class TextStyle:
    """Visual text settings used to render text into a Layer surface."""

    font_name: str | None = None
    font_path: str | None = None
    font_size: int = 24
    color: tuple[int, int, int] = (255, 255, 255)
    antialias: bool = True

    def to_manifest_entry(self):
        """Return serializable text style metadata for GuiManifest."""
        return {
            "font_name": self.font_name,
            "font_path": self.font_path,
            "font_size": self.font_size,
            "color": list(self.color),
            "antialias": self.antialias,
        }


def create_text_layer(
    layer_name,
    text,
    size=None,
    style=None,
    position=(0, 0),
    text_key=None,
    fit_mode="none",
    scale_percent=(100, 100),
):
    """Create a normal Layer whose frame is a rendered text surface."""
    style = style or TextStyle()
    scale_percent = normalize_scale_percent(scale_percent)
    return Layer(
        name=layer_name,
        frames=[render_text_surface(text, style, size, fit_mode, scale_percent)],
        position=position,
        layer_type="text",
        text_key=text_key,
        default_text=str(text),
        size=size,
        scale_percent=scale_percent,
        fit_mode=fit_mode,
        style=style,
    )


def render_text_surface(text, style, size=None, fit_mode="none", scale_percent=(100, 100)):
    """Render text into a pygame.Surface, optionally fitted into a fixed rect."""
    if not pygame.font.get_init():
        pygame.font.init()

    font = get_text_font(style)
    text_surface = font.render(str(text), style.antialias, style.color)
    scale_percent = normalize_scale_percent(scale_percent)
    if size is None:
        return scale_surface_percent(text_surface, scale_percent)

    size = normalize_text_rect_size(size)
    surface = pygame.Surface(size, pygame.SRCALPHA)
    fitted_surface = fit_text_surface(text_surface, size, fit_mode)
    fitted_surface = scale_surface_percent(fitted_surface, scale_percent)
    surface.blit(fitted_surface, fitted_surface.get_rect(center=surface.get_rect().center))
    return surface


def get_text_font(style):
    """Return a pygame Font from a TextStyle."""
    if style.font_path:
        return pygame.font.Font(resolve_project_path(style.font_path), style.font_size)
    if style.font_name:
        return pygame.font.SysFont(style.font_name, style.font_size)
    return pygame.font.Font(None, style.font_size)


def resolve_project_path(path):
    """Resolve project-relative paths used by GUI layer metadata."""
    if os.path.isabs(path):
        return path
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(project_dir, path)


def normalize_text_rect_size(size):
    """Return a safe pygame size tuple for a text layer rect."""
    width, height = size
    return normalize_positive_int(width, 1), normalize_positive_int(height, 1)


def normalize_scale_percent(scale_percent):
    """Return safe separate width/height scale percentages."""
    if scale_percent is None:
        return 100, 100
    if isinstance(scale_percent, dict):
        width = scale_percent.get("w", scale_percent.get("x", 100))
        height = scale_percent.get("h", scale_percent.get("y", 100))
        return normalize_positive_int(width, 100), normalize_positive_int(height, 100)
    if isinstance(scale_percent, (int, float)):
        value = normalize_positive_int(scale_percent, 100)
        return value, value
    if isinstance(scale_percent, str):
        values = [part.strip() for part in scale_percent.split(",")]
    else:
        try:
            values = list(scale_percent)
        except TypeError:
            return 100, 100
    while len(values) < 2:
        values.append(100)
    return normalize_positive_int(values[0], 100), normalize_positive_int(values[1], 100)


def normalize_positive_int(value, default):
    """Return a positive int from UI/config values such as 70, 70.0, or '70%'."""
    try:
        if isinstance(value, str):
            value = value.strip().rstrip("%")
            if not value:
                return int(default)
        return max(1, int(float(value)))
    except (TypeError, ValueError):
        return int(default)


def scale_surface_percent(surface, scale_percent):
    """Scale surface separately by width and height percentages."""
    scale_w, scale_h = normalize_scale_percent(scale_percent)
    width, height = surface.get_size()
    size = (
        max(1, round(width * scale_w / 100)),
        max(1, round(height * scale_h / 100)),
    )
    if size == surface.get_size():
        return surface
    return pygame.transform.smoothscale(surface, size)


def fit_text_surface(surface, target_size, fit_mode="none"):
    """Scale rendered text using pygame transforms according to fit_mode."""
    fit_mode = normalize_text_fit_mode(fit_mode)
    if fit_mode == "none":
        return surface

    source_width, source_height = surface.get_size()
    if source_width <= 0 or source_height <= 0:
        return surface

    target_width, target_height = target_size
    if fit_mode == "width":
        scale = target_width / source_width
        size = (target_width, max(1, round(source_height * scale)))
    elif fit_mode == "height":
        scale = target_height / source_height
        size = (max(1, round(source_width * scale)), target_height)
    elif fit_mode == "contain":
        scale = min(target_width / source_width, target_height / source_height)
        size = (
            max(1, round(source_width * scale)),
            max(1, round(source_height * scale)),
        )
    elif fit_mode == "stretch":
        size = (target_width, target_height)
    else:
        raise ValueError(f"Unsupported text fit mode: {fit_mode}")

    if size == surface.get_size():
        return surface
    return pygame.transform.smoothscale(surface, size)


def normalize_text_fit_mode(fit_mode):
    """Normalize text fit mode aliases used by GUI builders and manifests."""
    if fit_mode is None:
        return "none"

    fit_mode = str(fit_mode).strip().lower()
    aliases = {
        "": "none",
        "no": "none",
        "off": "none",
        "both": "contain",
        "box": "contain",
        "width_height": "contain",
        "width+height": "contain",
        "fill": "stretch",
    }
    return aliases.get(fit_mode, fit_mode)


class Group(BaseGroup):
    """Пассивный drawable-объект с rect, hit_rect, scale_factor и слоями кадров.

    Group не различает статику и анимацию. Любой PNG после ResourceManager
    становится списком кадров: обычная картинка - это список из одного кадра,
    spritesheet - список из нескольких кадров. Activity может менять текущий
    кадр слоя, позицию group-а и scale_factor, но не правила игры.
    """

    def __init__(
        self,
        group_id,
        rect=(0, 0, 0, 0),
        hit_rect=None,
        layers=None,
        scale_factor=1.0,
        role=None,
        tags=None,
        manifest_targets=None,
    ):
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
        self.parent_frame = None
        self._rect = self._base_rect.copy()
        self._base_hit_rect = pygame.Rect(hit_rect) if hit_rect is not None else self._base_rect.copy()
        self._hit_rect = self._base_hit_rect.copy()
        self.scale_factor = float(scale_factor)
        self.hide_rect = True
        self.rect_debug_layer_ids = None
        self.role = role
        self.tags = frozenset(tags or ())
        self.manifest_targets = dict(manifest_targets or {})
        self.layers = []

        for layer in layers or []:
            self.add_layer(layer)

        if self._base_rect.size == (0, 0):
            self.refresh_rect_from_layers()
        self.apply_scale()

    @classmethod
    def from_config(cls, group_id, resource_manager):
        """Create a Group by reading its metadata from group_config."""
        config = group_config.get_group_config(group_id)
        group = cls(
            group_id=group_id,
            rect=config.get("rect", (0, 0, 0, 0)),
            hit_rect=config.get("hit_rect"),
            scale_factor=config.get("scale_factor", 1.0),
            role=config.get("role"),
            tags=config.get("tags", ()),
            manifest_targets=cls.resolve_manifest_targets(group_id, config),
        )
        group.reload_layers_from_config(resource_manager)
        group.set_rect_visibility(
            config.get("hide_rect", True),
            config.get("rect_debug_layer_ids"),
        )
        return group

    @staticmethod
    def resolve_manifest_targets(group_id, config):
        """Attach group_id to public targets declared in group_config."""
        targets = {}
        for target_id, target_config in config.get("manifest_targets", {}).items():
            target = dict(target_config)
            target.setdefault("group_id", group_id)
            targets[target_id] = target
        return targets

    def reload_layers_from_config(self, resource_manager):
        """Rebuild all drawable layers from group_config."""
        config = group_config.get_group_config(self.id)
        self.layers = [
            self.create_layer_from_config(layer_config, resource_manager)
            for layer_config in config.get("layers", ())
        ]
        if self._base_rect.size == (0, 0):
            self.refresh_rect_from_layers()
            self.apply_scale()
        return self

    @classmethod
    def create_layer_from_config(cls, layer_config, resource_manager):
        """Create one runtime Layer from a group_config layer entry."""
        layer_type = layer_config.get("type", "image")
        if layer_type == "text":
            return create_text_layer(
                layer_config["name"],
                layer_config.get("text", ""),
                size=layer_config.get("size"),
                style=cls.create_text_style_from_config(layer_config.get("style", {})),
                position=cls.normalize_layer_position(layer_config.get("position", (0, 0))),
                text_key=layer_config.get("text_key"),
                fit_mode=layer_config.get("fit_mode", "none"),
                scale_percent=layer_config.get("scale_percent", (100, 100)),
            )

        resource_key = layer_config["resource_key"]
        return Layer(
            name=layer_config["name"],
            frames=resource_manager.get_frames(resource_key),
            position=cls.normalize_layer_position(layer_config.get("position", (0, 0))),
            layer_type="resource",
        )

    @staticmethod
    def create_text_style_from_config(style_config):
        """Create TextStyle from plain layer metadata."""
        if isinstance(style_config, TextStyle):
            return style_config
        return TextStyle(**dict(style_config))

    def set_layer_resource_from_config(self, layer_name, resource_key, resource_manager):
        """Update group_config and reload one image layer."""
        layer_config = group_config.set_layer_resource(self.id, layer_name, resource_key)
        self.replace_layer(self.create_layer_from_config(layer_config, resource_manager))
        return self.get_layer(layer_name)

    def set_layer_text_from_config(self, layer_name, text):
        """Update group_config and reload one text layer."""
        layer_config = group_config.set_layer_text(self.id, layer_name, text)
        self.replace_layer(self.create_layer_from_config(layer_config, None))
        return self.get_layer(layer_name)

    def replace_layer(self, layer):
        """Replace an existing layer while keeping draw order from group_config."""
        for index, existing_layer in enumerate(self.layers):
            if existing_layer.name == layer.name:
                self.layers[index] = layer
                return layer
        self.layers.append(layer)
        return layer

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
            layers.append(
                Layer(
                    layer_name,
                    resource_manager.get_frames(resource_key),
                    position,
                    layer_type="resource",
                    resource_key=resource_key,
                )
            )
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
        """Текущий прямоугольник group-а в координатах экрана."""
        return self.local_rect_to_screen_rect(self.get_scaled_local_rect())

    @property
    def hit_rect(self):
        """Обязательная область взаимодействия group-а в координатах экрана."""
        return self.local_rect_to_screen_rect(self.get_scaled_local_hit_rect())

    @property
    def local_rect(self):
        """Прямоугольник group-а в координатах parent Frame."""
        return self._base_rect.copy()

    @property
    def local_hit_rect(self):
        """Область взаимодействия group-а в координатах parent Frame."""
        return self._base_hit_rect.copy()

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

    def set_parent_frame(self, frame):
        """Назначить parent Frame для local -> screen преобразования."""
        self.parent_frame = frame
        self.apply_scale()
        return self

    def set_local_position(self, x, y):
        """Переместить group в локальных координатах parent Frame."""
        old_position = self._base_rect.topleft
        self._base_rect.topleft = (int(x), int(y))
        self._base_hit_rect.move_ip(
            self._base_rect.x - old_position[0],
            self._base_rect.y - old_position[1],
        )
        self.apply_scale()

    def set_position(self, x, y):
        """Совместимость: задать позицию в координатах экрана."""
        if self.parent_frame is None:
            self.set_local_position(x, y)
            return
        self.set_local_position(*self.parent_frame.to_local((x, y)))

    def set_local_rect(self, rect):
        """Задать rect group-а в координатах parent Frame."""
        self._base_rect = pygame.Rect(rect)
        self._base_hit_rect = self._base_rect.copy()
        self.apply_scale()

    def set_rect(self, rect):
        """Совместимость: задать rect group-а в координатах экрана."""
        screen_rect = pygame.Rect(rect)
        if self.parent_frame is None:
            self.set_local_rect(screen_rect)
            return
        local_pos = self.parent_frame.to_local(screen_rect.topleft)
        self.set_local_rect((*local_pos, screen_rect.width, screen_rect.height))

    def set_hit_rect(self, rect):
        """Задать область клика group-а в локальных координатах parent Frame.

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
        """Пересчитать screen rect/hit_rect от локальной геометрии и scale_factor."""
        self._rect = self.rect
        self._hit_rect = self.hit_rect

    def get_scaled_local_rect(self):
        """Return local rect with size scaled from its base top-left."""
        return self.scale_rect(self._base_rect, self.scale_factor)

    def get_scaled_local_hit_rect(self):
        """Return local hit rect with size scaled from its base top-left."""
        return self.scale_rect(self._base_hit_rect, self.scale_factor)

    def local_rect_to_screen_rect(self, rect):
        """Convert a local group rect to screen coordinates."""
        if self.parent_frame is None:
            return rect.copy()
        return pygame.Rect(self.parent_frame.to_screen(rect.topleft), rect.size)

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
        rect = self.rect
        return (
            rect.x + round(layer.position[0] * self.scale_factor),
            rect.y + round(layer.position[1] * self.scale_factor),
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

    def to_manifest_entry(self):
        """Return serializable group metadata for GuiManifest."""
        return {
            "id": self.id,
            "role": self.role,
            "tags": sorted(self.tags),
            "manifest_targets": self.manifest_targets,
            "local_rect": list(self.local_rect),
            "local_hit_rect": list(self.local_hit_rect),
            "rect": list(self.rect),
            "hit_rect": list(self.hit_rect),
            "scale_factor": self.scale_factor,
            "hide_rect": self.hide_rect,
            "rect_debug_layer_ids": (
                sorted(self.rect_debug_layer_ids)
                if self.rect_debug_layer_ids is not None
                else None
            ),
            "layer_order": [layer.name for layer in self.layers],
            "layers": {
                layer.name: layer.to_manifest_entry()
                for layer in self.layers
            },
        }

    @staticmethod
    def scale_rect(rect, scale_factor):
        """Масштабировать прямоугольник от его базовой левой верхней точки."""
        return pygame.Rect(
            rect.x,
            rect.y,
            max(0, round(rect.width * scale_factor)),
            max(0, round(rect.height * scale_factor)),
        )
