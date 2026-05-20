import pygame


class SandboxEngine:
    def __init__(self, asset_instance, screen_size=(800, 600)):
        pygame.init()
        self.screen = pygame.display.set_mode(screen_size)
        self.clock = pygame.time.Clock()
        self.asset = asset_instance
        self.target_rect = None  # Теперь мы зададим его снаружи

    def set_target_rect(self, rect: pygame.Rect):
        self.target_rect = rect

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(60) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            if self.asset:
                self.asset.update(dt)

            self.screen.fill((30, 30, 30))

            if self.asset and self.target_rect:
                self.asset.draw(self.screen, self.target_rect)

            pygame.display.flip()

        pygame.quit()