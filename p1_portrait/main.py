import os
import pygame
from core.engine import SandboxEngine
from portrait_p1_asset import PortraitP1

# --- КОНСТАНТЫ (ДИЛЕР КОНФИГА) ---
SCREEN_SIZE = (350, 350)
PORTRAIT_TARGET_RECT = pygame.Rect(0, 0, 350, 350)
ANIM_SPEED = 0.12  # Хочу чуть быстрее
FRAME_SIZE = (350, 350)

current_dir = os.path.dirname(os.path.abspath(__file__))

# 1. Запускаем движок (движок теперь просто исполнитель)
engine = SandboxEngine(None, screen_size=SCREEN_SIZE)
engine.set_target_rect(PORTRAIT_TARGET_RECT)

# 2. Создаем портрет с переданными константами
my_portrait = PortraitP1(
    asset_path=current_dir,
    frame_size=FRAME_SIZE
)

# 3. Передаем объект
engine.asset = my_portrait

# 4. Запуск
engine.run()