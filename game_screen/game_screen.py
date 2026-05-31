"""Базовый экран-сцена для экранных зон и активных GUI actor-ов."""

from base import BaseGameScreen


class GameScreen(BaseGameScreen):
    """Экран игры, который оркестрирует активные actor ID и Activity."""

    BG_COLOR = (30, 30, 30)

    def __init__(self, actor_store=None, game_controller=None, background_color=None):
        """Создать базовый экран.

        GameScreen не является складом всех графических объектов игры.
        Он хранит только ID тех actor-ов, которые должны участвовать именно
        в этой сцене. Сами GuiActor лежат в actor_store и достаются оттуда
        по стабильному ID.

        Args:
            actor_store: Контейнер GuiActor-ов, доступных по стабильному ID.
            game_controller: Контроллер игровой логики.
            background_color: Цвет очистки экрана. Если не передан, берется BG_COLOR.
        """
        # Общий контейнер графических объектов. Экран берет из него actor-ы
        # по ID, но не владеет всеми actor-ами игры напрямую.
        self.actor_store = actor_store

        # Контроллер игровой логики. Экран может передавать ему события ввода
        # и забирать визуальные запросы, но не хранит правила игры у себя.
        self.game_controller = game_controller

        # Цвет, которым экран очищается перед новой отрисовкой кадра.
        self.background_color = background_color or self.BG_COLOR

        # ID actor-ов, которые активны на этом экране прямо сейчас.
        # Например, на главном столе здесь могут быть ID карт, кнопок,
        # аватаров и элементов интерфейса, которые видимы в текущей сцене.
        self.active_actor_ids = []

        # Временные визуальные процессы: перемещение карты, появление,
        # исчезновение, проигрывание кадровой анимации и т.д.
        self.active_activities = []

        # Описание экранных зон: прямоугольники, точки привязки и правила
        # размещения actor-ов внутри конкретной сцены.
        self.screen_zones = {}

    def set_actor_store(self, actor_store):
        """Подключить контейнер GuiActor-ов после создания экрана.

        Метод нужен, если экран создается раньше, чем готов общий склад
        графических объектов, или если зависимости подключаются отдельным
        этапом в main.py.
        """
        self.actor_store = actor_store

    def set_game_controller(self, game_controller):
        """Подключить GameController после создания экрана.

        GameController остается владельцем правил и логического состояния.
        Экран использует его как источник решений и получатель событий ввода.
        """
        self.game_controller = game_controller

    def add_screen_zone(self, zone_id, zone_config):
        """Добавить или заменить экранную зону.

        Логическая зона живет в GameController, например bottom_hand как
        список card_id. Экранная зона живет здесь: это координаты и правила
        размещения этой зоны на конкретном экране.
        """
        self.screen_zones[zone_id] = zone_config

    def get_screen_zone(self, zone_id):
        """Вернуть описание экранной зоны по ID.

        Если зоны нет, Python выбросит KeyError. Это полезно на этапе
        разработки: ошибка сразу покажет, что экран не знает нужную зону.
        """
        return self.screen_zones[zone_id]

    def activate_actor(self, actor_id):
        """Добавить actor ID в активный набор текущего экрана.

        Actor уже должен существовать в actor_store. Экран только отмечает,
        что этот actor участвует в текущей сцене, и возвращает сам объект
        для дальнейшей настройки позиции, hit_rect или слоев.
        """
        if actor_id not in self.active_actor_ids:
            self.active_actor_ids.append(actor_id)
        return self.get_actor(actor_id)

    def deactivate_actor(self, actor_id):
        """Убрать actor ID из активного набора текущего экрана.

        Сам GuiActor при этом не удаляется из общего actor_store. Он просто
        перестает обновляться и рисоваться этим экраном.
        """
        if actor_id in self.active_actor_ids:
            self.active_actor_ids.remove(actor_id)

    def get_actor(self, actor_id):
        """Получить GuiActor из общего контейнера по ID.

        Это центральная точка связи экрана с графическими объектами:
        экран работает с ID, а конкретный объект достает из GuiActorStore.
        """
        if self.actor_store is None:
            raise RuntimeError("GameScreen.actor_store не подключен")
        return self.actor_store.get(actor_id)

    def iter_active_actors(self):
        """Итерировать активные GuiActor текущего экрана в порядке actor ID.

        Порядок списка active_actor_ids пока является порядком update/draw.
        Позже, когда появятся полноценные screen zones, этот порядок можно
        заменить на сортировку по зонам и слоям.
        """
        for actor_id in self.active_actor_ids:
            yield self.get_actor(actor_id)

    def add_activity(self, activity):
        """Добавить визуальную активность на экран.

        Activity получает ссылки на нужные GuiActor и меняет их визуальное
        состояние во времени. Она не должна менять правила игры напрямую.
        """
        self.active_activities.append(activity)
        if hasattr(activity, "start"):
            activity.start()
        return activity

    def handle_event(self, event):
        """Обработать событие Pygame.

        Базовый экран не реагирует на события, но оставляет контракт для
        наследников.
        """
        return True

    def update(self, dt):
        """Обновить активные визуальные процессы и активные actor-ы.

        Сначала обновляются Activity, потому что они могут поменять положение,
        прозрачность или кадр actor-а. После этого обновляются сами активные
        actor-ы. В будущей архитектуре GuiActor должен быть почти пассивным,
        поэтому этот второй цикл может стать очень легким.
        """
        self.update_activities(dt)

        for actor in self.iter_active_actors():
            actor.update(dt)

    def update_activities(self, dt):
        """Обновить Activity и убрать завершенные процессы.

        Activity живет только пока выполняется визуальный процесс. Когда она
        завершилась, экран убирает ее из active_activities, но не принимает
        игровых решений внутри самой Activity.
        """
        running_activities = []
        for activity in self.active_activities:
            activity.update(dt)
            if not self.is_activity_finished(activity):
                running_activities.append(activity)
        self.active_activities = running_activities

    @staticmethod
    def is_activity_finished(activity):
        """Проверить завершение Activity с поддержкой свойства или метода.

        На раннем этапе удобно поддерживать оба варианта:
        activity.is_finished как bool-свойство и activity.is_finished() как
        метод. Когда контракт Activity устоится, можно оставить один стиль.
        """
        is_finished = getattr(activity, "is_finished", False)
        if callable(is_finished):
            return is_finished()
        return bool(is_finished)

    def draw(self, screen):
        """Очистить экран и отрисовать активные actor-ы.

        Базовый экран рисует actor-ы в порядке active_actor_ids. Конкретные
        экраны могут переопределить draw, чтобы учитывать зоны, фон, UI и
        более строгий порядок слоев.
        """
        screen.fill(self.background_color)
        for actor in self.iter_active_actors():
            actor.draw(screen)
