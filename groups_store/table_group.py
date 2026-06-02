"""Сборка Group-а игрового стола.

Модуль не хранит общий GroupStore и не импортирует main.py. Его задача -
описать конкретный визуальный объект и вернуть готовый Group тому, кто
собирает общий склад графики.
"""

from group import Group


GROUP_ID = "table_group"
HIDE_RECT = False

GRAPHICS = (
    ("table", "main_screen.table", (0, 0)),
    ("tressure_map", "main_screen.tressure_map", (0, 0)),
)

GROUP_RECT = (0, 0, 1280, 720)


def create(resource_manager):
    """Создать Group стола из ресурсов главного экрана."""
    group = Group.create_group(
        GROUP_ID,
        GRAPHICS,
        rect=GROUP_RECT,
        resource_manager=resource_manager,
    )
    return group.set_rect_visibility(HIDE_RECT)

