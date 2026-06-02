"""РЎР±РѕСЂРєР° Group-Р° Р»РµРІРѕРіРѕ РёРіСЂРѕРєР°.

РњРѕРґСѓР»СЊ РЅРµ С…СЂР°РЅРёС‚ РѕР±С‰РёР№ GroupStore Рё РЅРµ РёРјРїРѕСЂС‚РёСЂСѓРµС‚ main.py. Р•РіРѕ Р·Р°РґР°С‡Р° -
РѕРїРёСЃР°С‚СЊ РєРѕРЅРєСЂРµС‚РЅС‹Р№ РІРёР·СѓР°Р»СЊРЅС‹Р№ РѕР±СЉРµРєС‚ Рё РІРµСЂРЅСѓС‚СЊ РіРѕС‚РѕРІС‹Р№ Group С‚РѕРјСѓ, РєС‚Рѕ
СЃРѕР±РёСЂР°РµС‚ РѕР±С‰РёР№ СЃРєР»Р°Рґ РіСЂР°С„РёРєРё.
"""

from group import Group


GROUP_ID = "left_player"

GRAPHICS = (
    ('p_portrait_bg', 'main_screen.p_portrait_bg'),
    ('portrait_2', 'main_screen.avatars.portrait_2'),
    ('portrait_frame', 'main_screen.portrait_frame'),
    ('p_name_bg', 'main_screen.p_name_bg'),
)

RECT = (0, 0, 160, 160)

def create(resource_manager):
    return Group.create_group(
        GROUP_ID,
        GRAPHICS,
        rect=RECT,
        resource_manager=resource_manager,
    )


