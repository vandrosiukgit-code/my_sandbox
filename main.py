"""Черновая точка входа проекта The Fool's Reef.

Логика игры и реальные игровые экраны еще находятся в разработке. Поэтому
main.py сейчас не запускает полноценный RenderEngine, а фиксирует будущую
схему сборки приложения в одном месте.
"""

from core import GameController
from gui_actor import GuiActorStore


SCREEN_SIZE = (1280, 720)
WINDOW_TITLE = "The Fool's Reef"


def build_app_context():
    """Собрать минимальный контекст приложения.

    Сейчас это заготовка будущего composition root. Здесь уже видно, какие
    крупные зависимости будут создаваться при старте игры:

    - GameController хранит fixture-состояние;
    - GuiActorStore будет хранить созданные GuiActor;
    - игровые экраны будут подключены позже отдельным этапом.
    """
    game_controller = GameController(GameController.create_fixture_state())
    actor_store = GuiActorStore()

    return {
        "game_controller": game_controller,
        "actor_store": actor_store,
        "screen_size": SCREEN_SIZE,
        "window_title": WINDOW_TITLE,
    }


def create_screen_factory(app_context):
    """Вернуть фабрику стартового экрана.

    Пока игровых экранов нет, фабрика намеренно возвращает None. Когда экран
    будет создан, именно здесь он получит game_controller и actor_store.
    """
    _ = app_context
    return None


def main():
    """Черновой запуск проекта.

    Сейчас функция только собирает контекст и выводит короткий статус. Полный
    запуск RenderEngine будет включен после появления актуального игрового
    экрана.
    """
    app_context = build_app_context()
    screen_factory = create_screen_factory(app_context)

    print(f"{app_context['window_title']}: app context prepared.")
    print(f"Fixture cards: {len(app_context['game_controller'].get_state().cards)}")
    print(f"GuiActorStore actors: {len(app_context['actor_store'])}")
    print(f"Screen factory ready: {screen_factory is not None}")


if __name__ == "__main__":
    main()
