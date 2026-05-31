"""Пассивный GUI/game-actor, собираемый из готовых Surface и кадров.

GuiActor больше не загружает ресурсы самостоятельно. По манифесту он не
должен знать о ResourceManager: внешний сборщик или будущая фабрика actor-ов
передает ему уже готовые pygame.Surface и списки кадров.
"""

import pygame

from base import BaseGuiActor


class GuiActor(BaseGuiActor):
    """Пассивный визуальный объект со слоями, rect и hit_rect.

    GuiActor хранит текущее визуальное состояние и умеет его рисовать. Он не
    принимает игровые решения, не знает правил игры и не управляет сложной
    анимацией во времени. Для временных процессов будут использоваться
    Activity: они меняют position, alpha, visible или current_frame через API
    этого actor-а.
    """

    def __init__(self, actor_id, position=(0, 0), static_surfaces=None, animation_frames=None, layers=None):
        """Создать GuiActor из готовых ресурсов.

        Args:
            actor_id: Стабильный ID. Такой же ID использует GameController,
                когда говорит экрану, какой объект нужно показать.
            position: Базовая точка actor-а в координатах экрана.
            static_surfaces: Словарь `resource_name -> pygame.Surface`.
            animation_frames: Словарь `resource_name -> list[pygame.Surface]`.
            layers: Список словарей слоев в порядке отрисовки.

        Пример слоя:

        ```python
        {
            "name": "card_face",
            "type": "static",
            "resource": "face",
            "offset": (0, 0),
            "visible": True,
            "alpha": 255,
        }
        ```
        """
        if not actor_id:
            raise ValueError("GuiActor требует непустой actor_id")

        self.actor_id = actor_id
        self.position = position

        # Это уже готовые ресурсы, полученные снаружи. GuiActor только хранит
        # ссылки на них и рисует. Загрузка PNG остается задачей ResourceManager
        # и будущей фабрики графических объектов.
        self.static_surfaces = static_surfaces or {}
        self.animation_frames = animation_frames or {}

        # Слои нормализуются при создании, чтобы дальше код мог работать с
        # единым набором ключей: name, type, resource, offset, visible, alpha,
        # frame_index.
        self.layers = [self.create_layer_state(layer) for layer in (layers or [])]

        self._rect = pygame.Rect(position, (0, 0))
        self._hit_rect = self._rect.copy()
        self.refresh_rect()

    @property
    def id(self):
        """Стабильный ID actor-а для связи логики и визуального слоя."""
        return self.actor_id

    @property
    def rect(self):
        """Базовый rect actor-а в координатах экрана."""
        return self._rect

    @property
    def hit_rect(self):
        """Область взаимодействия actor-а в координатах экрана."""
        return self._hit_rect

    def update(self, dt):
        """Обновить actor.

        Метод намеренно пустой. GuiActor не проигрывает анимацию сам:
        сменой кадров, перемещением и прозрачностью будут управлять Activity.
        Аргумент dt оставлен, потому что RenderEngine и GameScreen работают с
        единым контрактом update(dt).
        """
        _ = dt

    def draw(self, screen):
        """Отрисовать видимые слои actor-а в заданном порядке."""
        base_x, base_y = self.rect.topleft

        for layer in self.layers:
            if not layer["visible"]:
                continue

            surface = self.get_layer_surface(layer)
            if surface is None:
                continue

            draw_position = (
                base_x + layer["offset"][0],
                base_y + layer["offset"][1],
            )
            screen.blit(self.apply_layer_alpha(surface, layer["alpha"]), draw_position)

    def set_position(self, x, y):
        """Поставить базовый rect actor-а в координаты общего экрана.

        hit_rect двигается вместе с actor-ом. Если конкретному объекту нужна
        особая область клика, ее можно назначить повторно через set_hit_rect().
        """
        old_position = self._rect.topleft
        self.position = (x, y)
        self._rect.topleft = (x, y)

        dx = x - old_position[0]
        dy = y - old_position[1]
        self._hit_rect.move_ip(dx, dy)

    def set_hit_rect(self, rect):
        """Назначить область взаимодействия actor-а.

        hit_rect может отличаться от визуального rect. Например, у карты
        можно сделать область клика меньше декоративной тени.
        """
        self._hit_rect = pygame.Rect(rect)

    def set_layer_offset(self, layer_name, offset):
        """Сдвинуть слой относительно базового rect actor-а."""
        layer = self.get_layer(layer_name)
        layer["offset"] = tuple(offset)
        self.refresh_rect(keep_hit_rect=True)

    def set_layer_alpha(self, layer_name, alpha):
        """Изменить прозрачность слоя в диапазоне 0..255."""
        layer = self.get_layer(layer_name)
        layer["alpha"] = max(0, min(255, int(alpha)))

    def set_layer_visible(self, layer_name, visible):
        """Показать или скрыть слой."""
        layer = self.get_layer(layer_name)
        layer["visible"] = bool(visible)

    def set_layer_frame(self, layer_name, frame_index):
        """Установить текущий кадр кадрового слоя."""
        layer = self.get_layer(layer_name)
        if layer["type"] != "animation":
            raise ValueError(f"Слой не является кадровым: {layer_name}")

        frames = self.animation_frames.get(layer["resource"], [])
        if not frames:
            layer["frame_index"] = 0
            return

        layer["frame_index"] = max(0, min(int(frame_index), len(frames) - 1))

    def get_layer(self, layer_name):
        """Найти слой по имени или resource.

        name - предпочтительный идентификатор слоя. Поддержка resource нужна,
        чтобы старые конфигурации могли обращаться к слою по имени ресурса.
        """
        for layer in self.layers:
            if layer["name"] == layer_name or layer["resource"] == layer_name:
                return layer
        raise ValueError(f"Неизвестный слой: {layer_name}")

    def get_layer_surface(self, layer):
        """Вернуть текущую surface слоя."""
        if layer["type"] == "static":
            return self.static_surfaces.get(layer["resource"])

        if layer["type"] == "animation":
            frames = self.animation_frames.get(layer["resource"], [])
            if not frames:
                return None
            return frames[layer["frame_index"]]

        raise ValueError(f"Неизвестный тип слоя: {layer['type']}")

    def refresh_rect(self, keep_hit_rect=False):
        """Пересчитать размер rect по всем слоям actor-а.

        Rect строится как bounding box всех доступных surface с учетом offset.
        Это дает actor-у базовую геометрию даже без ручного задания размера.

        Args:
            keep_hit_rect: Если True, область клика не пересоздается. Это
                нужно, когда hit_rect был настроен вручную.
        """
        bounds = []
        for layer in self.layers:
            surface = self.get_layer_surface(layer)
            if surface is None:
                continue
            bounds.append(pygame.Rect(layer["offset"], surface.get_size()))

        if not bounds:
            self._rect = pygame.Rect(self.position, (0, 0))
            if not keep_hit_rect:
                self._hit_rect = self._rect.copy()
            return

        local_rect = bounds[0].copy()
        for rect in bounds[1:]:
            local_rect.union_ip(rect)

        self._rect = pygame.Rect(
            self.position[0],
            self.position[1],
            local_rect.width,
            local_rect.height,
        )
        if not keep_hit_rect:
            self._hit_rect = self._rect.copy()

    @staticmethod
    def create_layer_state(layer):
        """Вернуть нормализованный словарь состояния слоя.

        На вход можно передать неполное описание. Метод добавит значения по
        умолчанию, чтобы остальной код не был завален проверками.
        """
        resource_name = layer["resource"]
        return {
            "name": layer.get("name", resource_name),
            "type": layer["type"],
            "resource": resource_name,
            "offset": tuple(layer.get("offset", (0, 0))),
            "visible": layer.get("visible", True),
            "alpha": layer.get("alpha", 255),
            "frame_index": layer.get("frame_index", 0),
        }

    @staticmethod
    def apply_layer_alpha(surface, alpha):
        """Вернуть surface с учетом alpha слоя.

        При полной непрозрачности возвращается исходная surface. При другом
        alpha создается копия, чтобы не менять общий ресурс, который может
        использоваться несколькими actor-ами.
        """
        if alpha >= 255:
            return surface

        surface = surface.copy()
        surface.set_alpha(alpha)
        return surface
