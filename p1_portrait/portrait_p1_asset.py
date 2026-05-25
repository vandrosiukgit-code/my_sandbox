import os

import pygame

from core.base import BaseAsset
from core.engine import SandboxEngine
from core.resource import ResourceManager


class PortraitP1(BaseAsset):
    def __init__(self, rect, static_assets_dir, anim_assets_dir, anim_speed=0.12):
        super().__init__()
        self.rect = rect
        self.static_assets_dir = static_assets_dir
        self.anim_assets_dir = anim_assets_dir
        self.anim_speed = anim_speed
        self.anim_timer = 0.0
        self.anim_frame_index = 0

        self.portrait_path = os.path.join(static_assets_dir, "p1_portrait_sheet.png")
        self.frame_path = os.path.join(static_assets_dir, "p1_portrait_frame.png")
        self.shield_crush_path = os.path.join(anim_assets_dir, "shield_crush_anim_6f.png")

        ResourceManager.add_to_cache_static(static_assets_dir)
        ResourceManager.add_to_cache_anim(anim_assets_dir)

        self.portrait_img = ResourceManager.get_static(self.portrait_path)
        self.frame_img = ResourceManager.get_static(self.frame_path)
        self.shield_crush_frames = ResourceManager.get_animation(self.shield_crush_path)

    def update(self, dt):
        if not self.shield_crush_frames:
            return

        self.anim_timer += dt
        if self.anim_timer >= self.anim_speed:
            self.anim_timer -= self.anim_speed
            self.anim_frame_index = (self.anim_frame_index + 1) % len(self.shield_crush_frames)

    def draw(self, screen):
        # Отрисовка слоями: портрет, анимация, рамка.
        self.draw_centered(screen, self.portrait_img)
        self.draw_centered(screen, self.shield_crush_frames[self.anim_frame_index])
        self.draw_centered(screen, self.frame_img)

    def draw_centered(self, screen, surface):
        target = surface.get_rect(center=self.rect.center)
        screen.blit(surface, target)


# --- Логика запуска (бывший main.py) ---
def run():
    # Инициализация экрана
    current_dir = os.path.dirname(os.path.abspath(__file__))
    static_assets_dir = os.path.join(current_dir, "assets", "static")
    anim_assets_dir = os.path.join(current_dir, "assets", "animation")
    screen_size = (800, 800)
    portrait_rect = pygame.Rect(0, 0, *screen_size)

    # Инициализация PortraitP1
    engine = SandboxEngine(None, screen_size=screen_size)
    portrait = PortraitP1(
        rect=portrait_rect,
        static_assets_dir=static_assets_dir,
        anim_assets_dir=anim_assets_dir,
    )

    # Отрисовка экрана через draw
    engine.asset = portrait
    engine.run()


if __name__ == "__main__":
    run()
