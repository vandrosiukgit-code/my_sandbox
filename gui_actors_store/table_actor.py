"""Сборка GuiActor-а игрового стола.

Модуль не хранит общий GuiActorStore и не импортирует main.py. Его задача -
описать конкретный визуальный объект и вернуть готовый GuiActor тому, кто
собирает общий склад графики.
"""

from gui_actor import GuiActor


def create(resource_manager):
    """Создать GuiActor стола из ресурсов главного экрана."""
    graphics = (
        ("table", "main_screen.table"),
        ("tressure_map", "main_screen.tressure_map"),
    )
    return GuiActor.create_actor(
        "table_actor",
        graphics,
        rect=(0, 0, 1280, 720),
        resource_manager=resource_manager,
    )
