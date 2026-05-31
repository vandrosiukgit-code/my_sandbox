"""Графический runtime проекта: окно, события, update/draw loop."""

import pygame


class RenderEngine:
    """Pygame runner для одного активного экрана игры."""

    def __init__(self, screen_factory, screen_size=(800, 600), title="Sandbox"):
        """Создать окно и активный экран.

        Args:
            screen_factory: Фабрика экрана. Вызывается после создания display.
            screen_size: Размер окна Pygame в пикселях.
            title: Заголовок окна.
        """
        pygame.init()
        self.screen = pygame.display.set_mode(screen_size)
        pygame.display.set_caption(title)
        self.clock = pygame.time.Clock()
        self.game_screen = screen_factory()

    def run(self):
        """Запустить главный графический цикл."""
        running = True
        while running:
            dt = self.clock.tick(60) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif self.game_screen.handle_event(event) is False:
                    running = False

            self.game_screen.update(dt)
            self.game_screen.draw(self.screen)
            pygame.display.flip()

        pygame.quit()
