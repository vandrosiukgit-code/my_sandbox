"""Фабрика GuiActor-ов.

Фабрика является мостом между ResourceManager и пассивным GuiActor:

- ResourceManager знает, как загрузить PNG и spritesheet в общий кэш;
- GuiActor знает, как хранить и рисовать уже готовые Surface/frames;
- GuiActorFactory знает, какие ресурсы нужны конкретному actor-у.

Так мы не возвращаем загрузку ресурсов внутрь GuiActor и не раздуваем
GameScreen кодом сборки каждого визуального объекта.
"""

from core.resource import ResourceManager
from gui_actor.gui_actor import GuiActor
from gui_actor.gui_actor_store import GuiActorStore


class GuiActorFactory:
    """Сборщик GuiActor-ов из resource keys и описаний слоев."""

    def __init__(self, resource_manager=ResourceManager):
        """Создать фабрику.

        Args:
            resource_manager: Объект с API ResourceManager. По умолчанию
                используется текущий глобальный ResourceManager проекта.

        Фабрика не хранит actor-ы. Она только создает их. Хранение остается
        обязанностью GuiActorStore.
        """
        self.resource_manager = resource_manager

    def create_actor(
        self,
        actor_id,
        position=(0, 0),
        static_resources=None,
        animation_resources=None,
        layers=None,
    ):
        """Создать универсальный GuiActor из описания ресурсов и слоев.

        Args:
            actor_id: Стабильный ID будущего GuiActor.
            position: Базовая позиция actor-а на экране.
            static_resources: Словарь `local_name -> resource_key`.
            animation_resources: Словарь `local_name -> resource_key`.
            layers: Список слоев, где `resource` ссылается на local_name.

        Пример:

        ```python
        factory.create_actor(
            actor_id="card_17",
            static_resources={"face": "cards.a_of_clubs"},
            layers=[{"name": "face", "type": "static", "resource": "face"}],
        )
        ```
        """
        static_surfaces = self.get_static_surfaces(static_resources or {})
        animation_frames = self.get_animation_frames(animation_resources or {})

        return GuiActor(
            actor_id=actor_id,
            position=position,
            static_surfaces=static_surfaces,
            animation_frames=animation_frames,
            layers=layers or [],
        )

    def create_static_actor(self, actor_id, resource_key, position=(0, 0), layer_name="main"):
        """Создать actor из одного статического изображения.

        Метод удобен для фонов, кнопок, иконок, аватаров и простых картинок,
        где нужен один слой без дополнительной конфигурации.
        """
        return self.create_actor(
            actor_id=actor_id,
            position=position,
            static_resources={layer_name: resource_key},
            layers=[
                {
                    "name": layer_name,
                    "type": "static",
                    "resource": layer_name,
                    "offset": (0, 0),
                }
            ],
        )

    def create_card_actor(self, actor_id, card_face_key, card_back_key=None, position=(0, 0)):
        """Создать базовый actor игральной карты.

        У карты есть обязательный слой face и опциональный слой back. Видимость
        этих слоев позже сможет переключать Activity или GameScreen, не меняя
        игровую модель карты.
        """
        static_resources = {"face": card_face_key}
        layers = [
            {
                "name": "face",
                "type": "static",
                "resource": "face",
                "offset": (0, 0),
                "visible": True,
            }
        ]

        if card_back_key is not None:
            static_resources["back"] = card_back_key
            layers.append(
                {
                    "name": "back",
                    "type": "static",
                    "resource": "back",
                    "offset": (0, 0),
                    "visible": False,
                }
            )

        return self.create_actor(
            actor_id=actor_id,
            position=position,
            static_resources=static_resources,
            layers=layers,
        )

    def create_store(self, actor_configs):
        """Создать GuiActorStore из набора конфигураций.

        Args:
            actor_configs: Итерируемый набор словарей. Каждый словарь должен
                подходить для create_actor(). Это временный простой формат до
                появления более строгих конфигов/датаклассов.

        Returns:
            GuiActorStore, наполненный созданными actor-ами.
        """
        store = GuiActorStore()
        for config in actor_configs:
            store.add(self.create_actor(**config))
        return store

    def get_static_surfaces(self, resources):
        """Получить готовые Surface для статических ресурсов.

        На входе local_name -> resource_key. На выходе local_name -> Surface.
        Благодаря этому GuiActor не знает глобальные resource keys и работает
        только с локальными именами своих слоев.
        """
        return {
            local_name: self.resource_manager.get_static(resource_key)
            for local_name, resource_key in resources.items()
        }

    def get_animation_frames(self, resources):
        """Получить готовые списки кадров для анимационных ресурсов.

        На входе local_name -> resource_key. На выходе local_name -> frames.
        Смена кадров остается задачей Activity, а не GuiActor.
        """
        return {
            local_name: self.resource_manager.get_animation(resource_key)
            for local_name, resource_key in resources.items()
        }
