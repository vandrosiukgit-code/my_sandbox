"""Базовые контракты архитектуры The Fool's Reef.

Этот модуль задает минимальные правила взаимодействия между крупными
частями проекта. Здесь не должно быть игровой логики, загрузки ресурсов или
отрисовки. Только контракты: какие методы обязаны существовать у экранов,
акторов, активностей и контроллера.
"""

from abc import ABC, abstractmethod


class BaseGameScreen(ABC):
    """Базовый контракт экрана игры, которым управляет RenderEngine.

    Экран является визуальной сценой: он принимает события ввода, обновляет
    временные визуальные процессы и рисует текущий набор активных group-ов.
    Правила игры должны оставаться в GameController.
    """

    @abstractmethod
    def handle_event(self, event):
        """Обработать событие Pygame.

        Returns:
            False, если экран просит завершить главный цикл.
        """
        pass

    @abstractmethod
    def update(self, dt):
        """Обновить состояние экрана, Activity и активных group-ов."""
        pass

    @abstractmethod
    def draw(self, screen):
        """Отрисовать экран на переданной поверхности Pygame."""
        pass


class BaseGameController(ABC):
    """Базовый контракт контроллера игровой логики.

    GameController владеет правилами и логическим состоянием игры. Он не
    должен знать о pygame, Group, координатах экрана и Surface.
    """

    @abstractmethod
    def start_game(self):
        """Инициализировать игровое состояние."""
        pass

    @abstractmethod
    def on_group_clicked(self, group_id):
        """Принять событие клика по group ID от активного GameScreen."""
        pass

    @abstractmethod
    def get_state(self):
        """Вернуть текущий snapshot игрового состояния."""
        pass


class BaseActivity(ABC):
    """Базовый контракт визуально-поведенческого режима или процесса.

    Activity управляет визуальным поведением во времени: размещением Group,
    сменой кадров, запуском коротких Action или собственными generated
    visual-only Group. Activity не меняет правила игры напрямую и не владеет
    жизненным циклом игровых сущностей.
    """

    @abstractmethod
    def start(self):
        """Запустить визуальный режим/процесс."""
        pass

    @abstractmethod
    def update(self, dt):
        """Обновить визуальный режим/процесс на шаг dt."""
        pass

    @abstractmethod
    def is_finished(self):
        """Вернуть True, если визуальный режим/процесс завершен."""
        pass

    @abstractmethod
    def finish(self):
        """Принудительно завершить визуальный режим/процесс."""
        pass


class BaseFrame(ABC):
    """Базовый контракт активной экранной зоны.

    Frame - это не игровая зона из правил, а экранный контейнер. Она
    знает координаты, область взаимодействия и список group ID, которые
    должны быть размещены внутри нее.
    """

    @property
    @abstractmethod
    def id(self):
        """Стабильный ID экранной зоны."""
        pass

    @property
    @abstractmethod
    def rect(self):
        """Прямоугольник зоны в координатах экрана."""
        pass

    @property
    @abstractmethod
    def hit_rect(self):
        """Область взаимодействия зоны в координатах экрана."""
        pass

    @abstractmethod
    def set_group_ids(self, group_ids):
        """Задать group ID, которые должны быть размещены в зоне."""
        pass

    @abstractmethod
    def add_group_id(self, group_id):
        """Добавить group ID в зону."""
        pass

    @abstractmethod
    def remove_group_id(self, group_id):
        """Убрать group ID из зоны."""
        pass

    @abstractmethod
    def calculate_group_position(self, index, group_count, group=None):
        """Рассчитать позицию group-а внутри зоны."""
        pass

    @abstractmethod
    def apply_layout(self, group_store):
        """Применить layout зоны к Group-ам из group_store."""
        pass

    @abstractmethod
    def contains_point(self, point):
        """Проверить, попадает ли точка в hit_rect зоны."""
        pass


class BaseGroup(ABC):
    """Базовый контракт GUI/game-group-а.

    Group является пассивным визуальным объектом. Он хранит local_rect и
    local_hit_rect в координатах parent Frame, предоставляет screen-space rect
    и hit_rect для отрисовки/hit-test, хранит scale_factor и набор
    слоев-кадров, но не должен принимать игровые решения. У слоя нет offset,
    visible и alpha. Если часть интерфейса должна иметь отдельное положение
    или поведение, она оформляется отдельным Group.
    """

    @property
    @abstractmethod
    def id(self):
        """Стабильный ID group-а, общий для логики и визуального слоя."""
        pass

    @property
    @abstractmethod
    def rect(self):
        """Screen-space rect холста group-а."""
        pass

    @property
    @abstractmethod
    def hit_rect(self):
        """Screen-space область взаимодействия group-а."""
        pass

    @abstractmethod
    def update(self, dt):
        """Обновить внутреннее состояние group-а.

        В целевой архитектуре этот метод должен оставаться легким: group
        рисует текущее состояние, а не управляет сложной анимацией сам.
        """
        pass

    @abstractmethod
    def draw(self, screen):
        """Отрисовать group-а на переданной поверхности Pygame."""
        pass

    @abstractmethod
    def set_position(self, x, y):
        """Совместимость: переместить group в координатах экрана."""
        pass

    @abstractmethod
    def set_hit_rect(self, rect):
        """Назначить область взаимодействия group-а."""
        pass

    @abstractmethod
    def set_scale_factor(self, scale_factor):
        """Задать масштаб всего group-а."""
        pass

    @abstractmethod
    def set_layer_frame(self, layer_name, frame_index):
        """Установить текущий кадр слоя."""
        pass

    @abstractmethod
    def set_layer_frames(self, layer_name, frames):
        """Заменить список кадров слоя."""
        pass
