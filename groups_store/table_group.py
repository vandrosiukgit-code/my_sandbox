"""РЎР±РѕСЂРєР° Group-Р° РёРіСЂРѕРІРѕРіРѕ СЃС‚РѕР»Р°.

РњРѕРґСѓР»СЊ РЅРµ С…СЂР°РЅРёС‚ РѕР±С‰РёР№ GroupStore Рё РЅРµ РёРјРїРѕСЂС‚РёСЂСѓРµС‚ main.py. Р•РіРѕ Р·Р°РґР°С‡Р° -
РѕРїРёСЃР°С‚СЊ РєРѕРЅРєСЂРµС‚РЅС‹Р№ РІРёР·СѓР°Р»СЊРЅС‹Р№ РѕР±СЉРµРєС‚ Рё РІРµСЂРЅСѓС‚СЊ РіРѕС‚РѕРІС‹Р№ Group С‚РѕРјСѓ, РєС‚Рѕ
СЃРѕР±РёСЂР°РµС‚ РѕР±С‰РёР№ СЃРєР»Р°Рґ РіСЂР°С„РёРєРё.
"""

from group import Group


GROUP_ID = "table_group"

GRAPHICS = (
    ("table", "main_screen.table"),
    ("tressure_map", "main_screen.tressure_map"),
)

RECT = (0, 0, 1280, 720)


def create(resource_manager):
    """РЎРѕР·РґР°С‚СЊ Group СЃС‚РѕР»Р° РёР· СЂРµСЃСѓСЂСЃРѕРІ РіР»Р°РІРЅРѕРіРѕ СЌРєСЂР°РЅР°."""
    return Group.create_group(
        GROUP_ID,
        GRAPHICS,
        rect=RECT,
        resource_manager=resource_manager,
    )


