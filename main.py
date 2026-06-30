"""Точка входа проекта The Fool's Reef.

main.py является composition root: здесь создаются крупные зависимости
приложения и задается порядок старта runtime. Игровые правила, отрисовка
group-ов и подготовка конкретных ресурсов живут в своих модулях.
"""

import os

from core import GameController
from core.render_engine import RenderEngine, ScreenTransition
from core.resource import ResourceManager
from core.settings_repository import SettingsRepository
from group import GroupStore
from screens import StartMenuScreen, TableScreen


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(PROJECT_DIR, "assets")
SCREEN_SIZE = (1280, 720)
START_MENU_SCREEN_SIZE = StartMenuScreen.SCREEN_SIZE
WINDOW_TITLE = "The Fool's Reef"
CONFIG_PATH = os.path.join(PROJECT_DIR, "config", "game_settings.json")


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
    def screen_factory(_render_context=None):
        ResourceManager.build_runtime_cache(app_context["assets_dir"])
        app_context["group_store"].build()
        return TableScreen(
            group_store=app_context["group_store"],
            game_controller=app_context["game_controller"],
        )

    return screen_factory


def create_start_menu_screen_factory(app_context):
    def table_screen_factory(_render_context=None):
        ResourceManager.build_runtime_cache(app_context["assets_dir"])
        app_context["group_store"].build()
        return TableScreen(
            group_store=app_context["group_store"],
            game_controller=app_context["game_controller"],
        )

    def start_menu_factory(_render_context=None):
        settings_repository = SettingsRepository(CONFIG_PATH)

        def start_game(_config):
            return ScreenTransition(
                screen_factory=table_screen_factory,
                screen_size=app_context["screen_size"],
                title=app_context["window_title"],
            )

        return StartMenuScreen(
            settings_repository=settings_repository,
            on_play=start_game,
        )

    return start_menu_factory


def main():
    """Запустить графический runtime с текущим стартовым экраном."""
    app_context = build_app_context()
    screen_factory = create_start_menu_screen_factory(app_context)
    render_engine = RenderEngine(
        screen_factory=screen_factory,
        screen_size=START_MENU_SCREEN_SIZE,
        title=app_context["window_title"],
    )
    render_engine.run()


if __name__ == "__main__":
    main()
