import os

import pygame

from p1_portrait.portrait_p1_asset import PortraitP1


class MainGameScreen:
    SCREEN_SIZE = (800, 800)
    BG_COLOR = (30, 30, 30)
    PORTRAIT_ANIMATION = "shield_crush"

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode(self.SCREEN_SIZE)
        pygame.display.set_caption("Main Game Screen")
        self.clock = pygame.time.Clock()
        self.running = True

        self.portrait_x = 0
        self.portrait_y = 0
        self.animation_paused = False
        self.animation_visible = True
        self.animation_speed = 3

        self.portrait = self.create_p1_portrait()
        self.portrait.set_frame_position(self.portrait_x, self.portrait_y)

    def create_p1_portrait(self):
        project_dir = os.path.dirname(os.path.abspath(__file__))
        portrait_dir = os.path.join(project_dir, "p1_portrait")
        static_assets_dir = os.path.join(portrait_dir, "assets", "static")
        anim_assets_dir = os.path.join(portrait_dir, "assets", "animation")
        portrait_rect = pygame.Rect(0, 0, *self.SCREEN_SIZE)

        return PortraitP1(
            rect=portrait_rect,
            static_assets_dir=static_assets_dir,
            anim_assets_dir=anim_assets_dir,
            anim_speed=self.animation_speed,
        )

    def run(self):
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()

        pygame.quit()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self.handle_keydown(event.key)

    def handle_keydown(self, key):
        if key == pygame.K_ESCAPE:
            self.running = False
        elif key == pygame.K_LEFT:
            self.move_portrait(-10, 0)
        elif key == pygame.K_RIGHT:
            self.move_portrait(10, 0)
        elif key == pygame.K_UP:
            self.move_portrait(0, -10)
        elif key == pygame.K_DOWN:
            self.move_portrait(0, 10)
        elif key == pygame.K_SPACE:
            self.toggle_animation_pause()
        elif key == pygame.K_r:
            self.portrait.send_animation_command(self.PORTRAIT_ANIMATION, "reset")
        elif key == pygame.K_s:
            self.portrait.send_animation_command(self.PORTRAIT_ANIMATION, "stop")
            self.animation_paused = True
        elif key == pygame.K_h:
            self.toggle_animation_visibility()
        elif key in (pygame.K_PLUS, pygame.K_EQUALS):
            self.set_animation_speed(max(0.1, self.animation_speed - 0.1))
        elif key == pygame.K_MINUS:
            self.set_animation_speed(self.animation_speed + 0.1)

    def move_portrait(self, dx, dy):
        self.portrait_x += dx
        self.portrait_y += dy
        self.portrait.set_frame_position(self.portrait_x, self.portrait_y)

    def toggle_animation_pause(self):
        if self.animation_paused:
            self.portrait.send_animation_command(self.PORTRAIT_ANIMATION, "play")
        else:
            self.portrait.send_animation_command(self.PORTRAIT_ANIMATION, "pause")
        self.animation_paused = not self.animation_paused

    def toggle_animation_visibility(self):
        if self.animation_visible:
            self.portrait.send_animation_command(self.PORTRAIT_ANIMATION, "hide")
        else:
            self.portrait.send_animation_command(self.PORTRAIT_ANIMATION, "show")
        self.animation_visible = not self.animation_visible

    def set_animation_speed(self, speed):
        self.animation_speed = speed
        self.portrait.send_animation_command(
            self.PORTRAIT_ANIMATION,
            "set_speed",
            speed=self.animation_speed,
        )

    def update(self, dt):
        self.portrait.update(dt)

    def draw(self):
        self.screen.fill(self.BG_COLOR)
        self.portrait.draw(self.screen)
        pygame.display.flip()


if __name__ == "__main__":
    MainGameScreen().run()
