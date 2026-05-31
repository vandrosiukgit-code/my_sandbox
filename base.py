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
    временные визуальные процессы и рисует текущий набор активных actor-ов.
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
        """Обновить состояние экрана, Activity и активных actor-ов."""
        pass

    @abstractmethod
    def draw(self, screen):
        """Отрисовать экран на переданной поверхности Pygame."""
        pass


class BaseGameController(ABC):
    """Базовый контракт контроллера игровой логики.

    GameController владеет правилами и логическим состоянием игры. Он не
    должен знать о pygame, GuiActor, координатах экрана и Surface.
    """

    @abstractmethod
    def start_game(self):
        """Инициализировать игровое состояние."""
        pass

    @abstractmethod
    def on_actor_clicked(self, actor_id):
        """Принять событие клика по actor ID от активного GameScreen."""
        pass

    @abstractmethod
    def get_state(self):
        """Вернуть текущий snapshot игрового состояния."""
        pass


class BaseActivity(ABC):
    """Базовый контракт временного визуального процесса.

    Activity управляет визуальным состоянием одного или нескольких GuiActor
    во времени: перемещением, появлением, исчезновением, сменой кадров.
    Activity не меняет правила игры напрямую.
    """

    @abstractmethod
    def start(self):
        """Запустить визуальный процесс."""
        pass

    @abstractmethod
    def update(self, dt):
        """Обновить визуальный процесс на шаг dt."""
        pass

    @abstractmethod
    def is_finished(self):
        """Вернуть True, если визуальный процесс завершен."""
        pass

    @abstractmethod
    def finish(self):
        """Принудительно завершить визуальный процесс."""
        pass


class BaseActiveZone(ABC):
    """Базовый контракт активной экранной зоны.

    ActiveZone - это не игровая зона из правил, а экранный контейнер. Она
    знает координаты, область взаимодействия и список actor ID, которые
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
    def set_actor_ids(self, actor_ids):
        """Задать actor ID, которые должны быть размещены в зоне."""
        pass

    @abstractmethod
    def add_actor_id(self, actor_id):
        """Добавить actor ID в зону."""
        pass

    @abstractmethod
    def remove_actor_id(self, actor_id):
        """Убрать actor ID из зоны."""
        pass

    @abstractmethod
    def calculate_actor_position(self, index, actor_count, actor=None):
        """Рассчитать позицию actor-а внутри зоны."""
        pass

    @abstractmethod
    def apply_layout(self, actor_store):
        """Применить layout зоны к GuiActor-ам из actor_store."""
        pass

    @abstractmethod
    def contains_point(self, point):
        """Проверить, попадает ли точка в hit_rect зоны."""
        pass


class BaseGuiActor(ABC):
    """Базовый контракт GUI/game-actor-а.

    GuiActor является пассивным визуальным объектом. Он хранит rect,
    обязательный hit_rect и набор слоев, но не должен принимать игровые
    решения. Любая сложная временная логика должна жить в Activity.
    """

    @property
    @abstractmethod
    def id(self):
        """Стабильный ID actor-а, общий для логики и визуального слоя."""
        pass

    @property
    @abstractmethod
    def rect(self):
        """Базовый rect actor-а в координатах экрана."""
        pass

    @property
    @abstractmethod
    def hit_rect(self):
        """Область взаимодействия actor-а в координатах экрана."""
        pass

    @abstractmethod
    def update(self, dt):
        """Обновить внутреннее состояние actor-а.

        В целевой архитектуре этот метод должен оставаться легким: actor
        рисует текущее состояние, а не управляет сложной анимацией сам.
        """
        pass

    @abstractmethod
    def draw(self, screen):
        """Отрисовать actor-а на переданной поверхности Pygame."""
        pass

    @abstractmethod
    def set_position(self, x, y):
        """Поставить базовый rect actor-а в координаты общего экрана."""
        pass

    @abstractmethod
    def set_hit_rect(self, rect):
        """Назначить область взаимодействия actor-а."""
        pass

    @abstractmethod
    def set_layer_offset(self, layer_name, offset):
        """Сдвинуть слой относительно базового rect actor-а."""
        pass

    @abstractmethod
    def set_layer_alpha(self, layer_name, alpha):
        """Изменить прозрачность слоя."""
        pass

    @abstractmethod
    def set_layer_visible(self, layer_name, visible):
        """Показать или скрыть слой."""
        pass

    @abstractmethod
    def set_layer_frame(self, layer_name, frame_index):
        """Установить текущий кадр слоя, если слой кадровый."""
        pass
