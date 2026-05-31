"""Контейнер созданных GuiActor-ов.

GuiActorStore - это общий склад визуальных объектов игры. Он не является
экраном, не знает правил игры и не запускает Activity. Его задача проще:
держать уже созданные GuiActor по стабильным ID и отдавать их активному
GameScreen по запросу.
"""


class GuiActorStore:
    """Единый контейнер GuiActor-ов, доступных по actor ID."""

    def __init__(self):
        """Создать пустой склад графических объектов.

        Ключ словаря - стабильный actor_id. Значение - объект GuiActor.
        Например:

        - "card_17" -> GuiActor карты;
        - "main_menu.play_button" -> GuiActor кнопки;
        - "table.background" -> GuiActor фона стола.
        """
        self._actors = {}

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
