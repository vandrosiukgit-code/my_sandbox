from gui_actor import GuiActor
from core.resource import ResourceManager


graphics = (
    ("table", "main_screen.table"),
    ("tressure_map", "main_screen.tressure_map"),
)
actor = GuiActor.create_actor(
    "table_actor",
    graphics,
    rect=(0, 0, 1280, 720),
    resource_manager=ResourceManager,
)
