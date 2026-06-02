"""Сборка Group-а левого игрока.

Модуль не хранит общий GroupStore и не импортирует main.py. Его задача -
описать конкретный визуальный объект и вернуть готовый Group тому, кто
собирает общий склад графики.
"""

from group import Group

HIDE_RECT = False
GROUP_ID = "left_player"

GRAPHICS = (
    ("p_portrait_bg", "main_screen.p_portrait_bg", (0, 0)),
    ("portrait_2", "main_screen.avatars.portrait_2", (0, 0)),
    ("portrait_frame", "main_screen.portrait_frame", (0, 0)),
    ("p_name_bg", "main_screen.p_name_bg", (0, 132)),
)

GROUP_RECT = (0, 0, 200, 200)


def create(resource_manager):
    group = Group.create_group(
        GROUP_ID,
        GRAPHICS,
        rect=GROUP_RECT,
        resource_manager=resource_manager,
    )
    return group.set_rect_visibility(HIDE_RECT, "p_name_bg")

