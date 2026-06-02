"""Контейнер созданных Group-ов.

GroupStore - это общий склад визуальных объектов игры. Он не является
экраном, не знает правил игры и не запускает Activity. Его задача проще:
держать уже созданные Group по стабильным ID и отдавать их активному
GameScreen по запросу.
"""

import pkgutil
from importlib import import_module


class GroupStore:
    """Единый контейнер Group-ов, доступных по group ID."""

    DEFAULT_BUILDER_PACKAGE = "groups_store"
    DEFAULT_BUILDER_MODULES = ()

    def __init__(self, resource_manager=None, builders=None, builder_modules=None):
        """Создать пустой склад графических объектов.

        Ключ словаря - стабильный group_id. Значение - объект Group.
        Например:

        - "card_17" -> Group карты;
        - "main_menu.play_button" -> Group кнопки;
        - "table.background" -> Group фона стола.

        Args:
            resource_manager: Общий ResourceManager, из которого builder-ы
                получают кадры для слоев Group.
            builders: Необязательный набор функций-сборщиков. Каждая функция
                получает resource_manager и возвращает один Group или список
                Group-ов.
            builder_modules: Необязательный набор путей к модулям-сборщикам.
                Модуль должен содержать функцию create(resource_manager).
        """
        self._groups = {}
        self.resource_manager = resource_manager
        self.builders = tuple(builders or ())
        self.builder_modules = (
            tuple(builder_modules)
            if builder_modules is not None
            else self.discover_builder_modules()
        )

    def build(self):
        """Собрать все зарегистрированные Group-ы.

        Это точка массовой инициализации графических объектов игры. Main.py не
        должен вручную знать, как устроен table_group, card_group или будущие
        group-ы меню. Он создает один общий GroupStore, а store вызывает
        компактные builder-функции конкретных group-модулей.

        Важно: builder-ы используют ResourceManager.get_frames(), поэтому
        runtime-кэш ресурсов должен быть собран заранее, после создания pygame
        display.
        """
        if self.resource_manager is None:
            raise RuntimeError("GroupStore.build() требует подключенный resource_manager")

        for builder in self.iter_builders():
            self.add_many(builder(self.resource_manager))
        return self

    def iter_builders(self):
        """Вернуть все builder-функции конкретных Group-модулей.

        Пути к модулям импортируются лениво, только во время build(). Так
        базовый пакет group не тянет конкретные group-ы при обычном импорте
        и не создает круговые зависимости.
        """
        for builder in self.builders:
            yield builder

        for module_path in self.builder_modules:
            module = import_module(module_path)
            builder = getattr(module, "create", None)
            if builder is not None:
                yield builder

    @classmethod
    def discover_builder_modules(cls, package_name=None):
        """Find group builder modules inside groups_store automatically."""
        package_name = package_name or cls.DEFAULT_BUILDER_PACKAGE
        package = import_module(package_name)
        return tuple(
            sorted(
                module_info.name
                for module_info in pkgutil.iter_modules(
                    package.__path__,
                    f"{package.__name__}.",
                )
                if not module_info.ispkg
                and not module_info.name.rsplit(".", 1)[-1].startswith("_")
            )
        )

    def add_many(self, groups):
        """Добавить один Group или коллекцию Group-ов.

        Builder конкретного модуля может вернуть один group или несколько. Store
        нормализует оба варианта, чтобы модули group-ов оставались простыми.
        """
        if groups is None:
            return ()

        if isinstance(groups, (list, tuple, set)):
            added = tuple(self.add(group) for group in groups)
        else:
            added = (self.add(groups),)
        return added

    def add(self, group):
        """Добавить Group в store.

        Group обязан иметь непустой `id`. Это главный мост между логическим
        миром GameController и визуальным миром GameScreen.

        Returns:
            Добавленный group, чтобы вызов можно было использовать цепочкой.
        """
        group_id = self.get_group_id(group)
        if group_id in self._groups:
            raise ValueError(f"Group с ID уже существует: {group_id}")

        self._groups[group_id] = group
        return group

    def get(self, group_id):
        """Вернуть Group по ID.

        Если group отсутствует, выбрасывается KeyError. Это лучше, чем тихо
        вернуть None: ошибка сразу покажет, что экран запросил объект, который
        не был создан при сборке графики.
        """
        try:
            return self._groups[group_id]
        except KeyError as error:
            raise KeyError(f"Group не найден в GroupStore: {group_id}") from error

    def has(self, group_id):
        """Проверить, есть ли Group с таким ID."""
        return group_id in self._groups

    def remove(self, group_id):
        """Удалить Group из store и вернуть удаленный объект.

        Обычно экран должен только активировать или деактивировать group ID.
        Удаление из store нужно для редких случаев, когда графический объект
        действительно больше не существует в рамках всей игры.
        """
        try:
            return self._groups.pop(group_id)
        except KeyError as error:
            raise KeyError(f"Нельзя удалить отсутствующий Group: {group_id}") from error

    def all_ids(self):
        """Вернуть все group ID в стабильном отсортированном порядке."""
        return tuple(sorted(self._groups))

    def clear(self):
        """Очистить store.

        Метод полезен для тестов, перезапуска песочницы или полной пересборки
        графических объектов при смене проекта/набора ресурсов.
        """
        self._groups.clear()

    def __len__(self):
        """Вернуть количество group-ов в store."""
        return len(self._groups)

    def __contains__(self, group_id):
        """Поддержать выражение `group_id in group_store`."""
        return self.has(group_id)

    @staticmethod
    def get_group_id(group):
        """Достать ID из Group и проверить его корректность."""
        group_id = getattr(group, "id", None)
        if not group_id:
            raise ValueError("GroupStore.add() требует group с непустым id")
        return group_id


