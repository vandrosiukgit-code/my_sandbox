"""РўРѕС‡РєР° РІС…РѕРґР° РїСЂРѕРµРєС‚Р° The Fool's Reef.

main.py СЏРІР»СЏРµС‚СЃСЏ composition root: Р·РґРµСЃСЊ СЃРѕР·РґР°СЋС‚СЃСЏ РєСЂСѓРїРЅС‹Рµ Р·Р°РІРёСЃРёРјРѕСЃС‚Рё
РїСЂРёР»РѕР¶РµРЅРёСЏ Рё Р·Р°РґР°РµС‚СЃСЏ РїРѕСЂСЏРґРѕРє СЃС‚Р°СЂС‚Р° runtime. РРіСЂРѕРІС‹Рµ РїСЂР°РІРёР»Р°, РѕС‚СЂРёСЃРѕРІРєР°
group-РѕРІ Рё РїРѕРґРіРѕС‚РѕРІРєР° РєРѕРЅРєСЂРµС‚РЅС‹С… СЂРµСЃСѓСЂСЃРѕРІ Р¶РёРІСѓС‚ РІ СЃРІРѕРёС… РјРѕРґСѓР»СЏС….
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
    """РЎРѕР±СЂР°С‚СЊ РјРёРЅРёРјР°Р»СЊРЅС‹Р№ РєРѕРЅС‚РµРєСЃС‚ РїСЂРёР»РѕР¶РµРЅРёСЏ.

    Р—РґРµСЃСЊ СЃРѕР·РґР°СЋС‚СЃСЏ РѕР±СЉРµРєС‚С‹ РІРµСЂС…РЅРµРіРѕ СѓСЂРѕРІРЅСЏ, РєРѕС‚РѕСЂС‹Рµ РґРѕР»Р¶РЅС‹ Р±С‹С‚СЊ РѕР±С‰РёРјРё РґР»СЏ
    runtime:

    - GameController С…СЂР°РЅРёС‚ fixture-СЃРѕСЃС‚РѕСЏРЅРёРµ;
    - GroupStore С…СЂР°РЅРёС‚ СЃРѕР·РґР°РЅРЅС‹Рµ Group;
    - ResourceManager РїРµСЂРµРґР°РµС‚СЃСЏ РІ store РєР°Рє РёСЃС‚РѕС‡РЅРёРє РєР°РґСЂРѕРІ.
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
    """Р’РµСЂРЅСѓС‚СЊ С„Р°Р±СЂРёРєСѓ СЃС‚Р°СЂС‚РѕРІРѕРіРѕ СЌРєСЂР°РЅР°.

    RenderEngine РІС‹Р·С‹РІР°РµС‚ СЌС‚Сѓ С„Р°Р±СЂРёРєСѓ РїРѕСЃР»Рµ СЃРѕР·РґР°РЅРёСЏ pygame display. Р­С‚Рѕ РІР°Р¶РЅРѕ:
    ResourceManager Р·Р°РіСЂСѓР¶Р°РµС‚ PNG С‡РµСЂРµР· convert_alpha(), Р° РѕРЅ С‚СЂРµР±СѓРµС‚ СѓР¶Рµ
    СЃРѕР·РґР°РЅРЅРѕРµ РѕРєРЅРѕ. РџРѕСЌС‚РѕРјСѓ runtime-РєСЌС€ Рё GroupStore СЃРѕР±РёСЂР°СЋС‚СЃСЏ РёРјРµРЅРЅРѕ С‚СѓС‚.
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
    """Р—Р°РїСѓСЃС‚РёС‚СЊ РіСЂР°С„РёС‡РµСЃРєРёР№ runtime СЃ С‚РµРєСѓС‰РёРј СЃС‚Р°СЂС‚РѕРІС‹Рј СЌРєСЂР°РЅРѕРј."""
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


