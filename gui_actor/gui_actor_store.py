"""Контейнер созданных GuiActor-ов.

GuiActorStore - это общий склад визуальных объектов игры. Он не является
экраном, не знает правил игры и не запускает Activity. Его задача проще:
держать уже созданные GuiActor по стабильным ID и отдавать их активному
GameScreen по запросу.
"""

from importlib import import_module


class GuiActorStore:
    """Единый контейнер GuiActor-ов, доступных по actor ID."""

    DEFAULT_BUILDER_MODULES = ("gui_actors_store.table_actor",)

    def __init__(self, resource_manager=None, builders=None, builder_modules=None):
        """Создать пустой склад графических объектов.

        Ключ словаря - стабильный actor_id. Значение - объект GuiActor.
        Например:

        - "card_17" -> GuiActor карты;
        - "main_menu.play_button" -> GuiActor кнопки;
        - "table.background" -> GuiActor фона стола.

        Args:
            resource_manager: Общий ResourceManager, из которого builder-ы
                получают кадры для слоев GuiActor.
            builders: Необязательный набор функций-сборщиков. Каждая функция
                получает resource_manager и возвращает один GuiActor или список
                GuiActor-ов.
            builder_modules: Необязательный набор путей к модулям-сборщикам.
                Модуль должен содержать функцию create(resource_manager).
        """
        self._actors = {}
        self.resource_manager = resource_manager
        self.builders = tuple(builders or ())
        self.builder_modules = tuple(builder_modules or self.DEFAULT_BUILDER_MODULES)

    def build(self):
        """Собрать все зарегистрированные GuiActor-ы.

        Это точка массовой инициализации графических объектов игры. Main.py не
        должен вручную знать, как устроен table_actor, card_actor или будущие
        actor-ы меню. Он создает один общий GuiActorStore, а store вызывает
        компактные builder-функции конкретных actor-модулей.

        Важно: builder-ы используют ResourceManager.get_frames(), поэтому
        runtime-кэш ресурсов должен быть собран заранее, после создания pygame
        display.
        """
        if self.resource_manager is None:
            raise RuntimeError("GuiActorStore.build() требует подключенный resource_manager")

        for builder in self.iter_builders():
            self.add_many(builder(self.resource_manager))
        return self

    def iter_builders(self):
        """Вернуть все builder-функции конкретных GuiActor-модулей.

        Пути к модулям импортируются лениво, только во время build(). Так
        базовый пакет gui_actor не тянет конкретные actor-ы при обычном импорте
        и не создает круговые зависимости.
        """
        for builder in self.builders:
            yield builder

        for module_path in self.builder_modules:
            module = import_module(module_path)
            yield module.create

    def add_many(self, actors):
        """Добавить один GuiActor или коллекцию GuiActor-ов.

        Builder конкретного модуля может вернуть один actor или несколько. Store
        нормализует оба варианта, чтобы модули actor-ов оставались простыми.
        """
        if actors is None:
            return ()

        if isinstance(actors, (list, tuple, set)):
            added = tuple(self.add(actor) for actor in actors)
        else:
            added = (self.add(actors),)
        return added

    def add(self, actor):
        """Добавить GuiActor в store.

        Actor обязан иметь непустой `id`. Это главный мост между логическим
        миром GameController и визуальным миром GameScreen.

        Returns:
            Добавленный actor, чтобы вызов можно было использовать цепочкой.
        """
        actor_id = self.get_actor_id(actor)
        if actor_id in self._actors:
            raise ValueError(f"GuiActor с ID уже существует: {actor_id}")

        self._actors[actor_id] = actor
        return actor

    def get(self, actor_id):
        """Вернуть GuiActor по ID.

        Если actor отсутствует, выбрасывается KeyError. Это лучше, чем тихо
        вернуть None: ошибка сразу покажет, что экран запросил объект, который
        не был создан при сборке графики.
        """
        try:
            return self._actors[actor_id]
        except KeyError as error:
            raise KeyError(f"GuiActor не найден в GuiActorStore: {actor_id}") from error

    def has(self, actor_id):
        """Проверить, есть ли GuiActor с таким ID."""
        return actor_id in self._actors

    def remove(self, actor_id):
        """Удалить GuiActor из store и вернуть удаленный объект.

        Обычно экран должен только активировать или деактивировать actor ID.
        Удаление из store нужно для редких случаев, когда графический объект
        действительно больше не существует в рамках всей игры.
        """
        try:
            return self._actors.pop(actor_id)
        except KeyError as error:
            raise KeyError(f"Нельзя удалить отсутствующий GuiActor: {actor_id}") from error

    def all_ids(self):
        """Вернуть все actor ID в стабильном отсортированном порядке."""
        return tuple(sorted(self._actors))

    def clear(self):
        """Очистить store.

        Метод полезен для тестов, перезапуска песочницы или полной пересборки
        графических объектов при смене проекта/набора ресурсов.
        """
        self._actors.clear()

    def __len__(self):
        """Вернуть количество actor-ов в store."""
        return len(self._actors)

    def __contains__(self, actor_id):
        """Поддержать выражение `actor_id in actor_store`."""
        return self.has(actor_id)

    @staticmethod
    def get_actor_id(actor):
        """Достать ID из GuiActor и проверить его корректность."""
        actor_id = getattr(actor, "id", None)
        if not actor_id:
            raise ValueError("GuiActorStore.add() требует actor с непустым id")
        return actor_id
