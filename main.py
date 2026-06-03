"""Точка входа проекта The Fool's Reef.

main.py является composition root: здесь создаются крупные зависимости
приложения и задается порядок старта runtime. Игровые правила, отрисовка
group-ов и подготовка конкретных ресурсов живут в своих модулях.
"""

import os

from core import GameController
from core.render_engine import RenderEngine
from core.resource import ResourceManager
from group import GroupStore
from screens.table_screen import TableScreen


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(PROJECT_DIR, "assets")
SCREEN_SIZE = (1280, 720)
WINDOW_TITLE = "The Fool's Reef"


def build_app_context():
    """Собрать минимальный контекст приложения.

    Здесь создаются объекты верхнего уровня, которые должны быть общими для
    runtime:

    - GameController хранит fixture-состояние;
    - GroupStore хранит созданные Group;
    - ResourceManager передается в store как источник кадров.
    """
    game_controller = GameController(GameController.create_fixture_state())
    group_store = GroupStore(resource_manager=ResourceManager)

    return {
        "game_controller": game_controller,
        "group_store": group_store,
        "assets_dir": ASSETS_DIR,
        "screen_size": SCREEN_SIZE,
        "window_title": WINDOW_TITLE,
    }


def create_screen_factory(app_context):
    """Вернуть фабрику стартового экрана.

    RenderEngine вызывает эту фабрику после создания pygame display. Это важно:
    ResourceManager загружает PNG через convert_alpha(), а он требует уже
    созданное окно. Поэтому runtime-кэш и GroupStore собираются именно тут.
    """
    def screen_factory():
        ResourceManager.build_runtime_cache(app_context["assets_dir"])
        app_context["group_store"].build()
        return TableScreen(
            group_store=app_context["group_store"],
            game_controller=app_context["game_controller"],
        )

    return screen_factory


def main():
    """Запустить графический runtime с текущим стартовым экраном."""
    app_context = build_app_context()
    screen_factory = create_screen_factory(app_context)
    render_engine = RenderEngine(
        screen_factory=screen_factory,
        screen_size=app_context["screen_size"],
        title=app_context["window_title"],
    )
    render_engine.run()


if __name__ == "__main__":
    main()
