from abc import ABC, abstractmethod


class BaseAsset(ABC):
    """Базовый контракт для всех игровых объектов."""

    @abstractmethod
    def update(self, dt):
        pass

    @abstractmethod
    def draw(self, screen):
        pass
