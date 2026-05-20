import pygame

class BaseAsset:
    def __init__(self, asset_path):
        self.asset_path = asset_path
    def update(self, dt):
        raise NotImplementedError()
    def draw(self, screen):
        raise NotImplementedError()