"""Сборка GuiActor-а игрового стола.

Модуль не хранит общий GuiActorStore и не импортирует main.py. Его задача -
описать конкретный визуальный объект и вернуть готовый GuiActor тому, кто
собирает общий склад графики.
"""

from gui_actor import GuiActor


ACTOR_ID = "table_actor"

GRAPHICS = (
    ("table", "main_screen.table"),
    ("tressure_map", "main_screen.tressure_map"),
)

RECT = (0, 0, 1280, 720)


def create(resource_manager):
    """Создать GuiActor стола из ресурсов главного экрана."""
    return GuiActor.create_actor(
        ACTOR_ID,
        GRAPHICS,
        rect=RECT,
        resource_manager=resource_manager,
    )
