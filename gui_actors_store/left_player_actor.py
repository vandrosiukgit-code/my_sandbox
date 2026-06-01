"""Сборка GuiActor-а левого игрока.

Модуль не хранит общий GuiActorStore и не импортирует main.py. Его задача -
описать конкретный визуальный объект и вернуть готовый GuiActor тому, кто
собирает общий склад графики.
"""

from gui_actor import GuiActor


ACTOR_ID = "left_player"

GRAPHICS = (
    ('p_portrait_bg', 'main_screen.p_portrait_bg'),
    ('portrait_2', 'main_screen.avatars.portrait_2'),
    ('portrait_frame', 'main_screen.portrait_frame'),
    ('p_name_bg', 'main_screen.p_name_bg'),
)

RECT = (0, 0, 160, 160)

def create(resource_manager):
    return GuiActor.create_actor(
        ACTOR_ID,
        GRAPHICS,
        rect=RECT,
        resource_manager=resource_manager,
    )
