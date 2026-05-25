import pygame

class SandboxEngine:
    def __init__(self, asset_instance, screen_size=(800, 600)):
        # Инициализируем библиотеку Pygame для работы с окном и графикой
        pygame.init()
        # Создаем окно заданного размера
        self.screen = pygame.display.set_mode(screen_size)
        # Создаем объект для управления частотой кадров (FPS)
        self.clock = pygame.time.Clock()
        # Сохраняем ссылку на объект (ассет), который будем обновлять и рисовать
        self.asset = asset_instance

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(60) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            # 1. ОБНОВЛЕНИЕ (обязательно добавьте, если еще нет)
            if self.asset:
                self.asset.update(dt)

            # 2. ОЧИСТКА ЭКРАНА (сначала заливаем фон)
            self.screen.fill((30, 30, 30))

            # 3. ОТРИСОВКА (рисуем поверх фона)
            if self.asset:
                self.asset.draw(self.screen)
            pygame.display.flip()
        pygame.quit()
