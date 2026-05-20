import pygame
import os
from core.base import BaseAsset


class PortraitP1(BaseAsset):
    def __init__(self, asset_path, frame_size=(110, 110)):
        super().__init__(asset_path)
        self.frame_width, self.frame_height = frame_size

        # Пути к ресурсам
        self.portrait_path = os.path.join(asset_path, "assets", "p1_portrait_sheet.png")
        self.frame_path = os.path.join(asset_path, "assets", "p1_portrait_frame.png")

        # Загрузка статичных изображений
        self.portrait_img = pygame.image.load(self.portrait_path).convert_alpha()
        self.frame_img = pygame.image.load(self.frame_path).convert_alpha()

    def update(self, dt: float):
        """Анимация отключена, метод пустой."""
        pass

    def draw(self, screen: pygame.Surface, rect: pygame.Rect):
        # 1. Рисуем портрет
        scaled_portrait = pygame.transform.smoothscale(self.portrait_img, rect.size)
        screen.blit(scaled_portrait, rect.topleft)

        # 2. Рисуем рамку поверх
        scaled_frame = pygame.transform.smoothscale(self.frame_img, rect.size)
        screen.blit(scaled_frame, rect.topleft)