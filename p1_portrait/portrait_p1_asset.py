import os

import pygame

from core.base import BaseAsset
from core.engine import SandboxEngine
from core.resource import ResourceManager


class PortraitP1(BaseAsset):
    ANIMATION_COMMANDS = {
        "play",
        "pause",
        "stop",
        "reset",
        "show",
        "hide",
        "set_speed",
        "set_loop",
    }

    def __init__(self, rect, static_assets_dir, anim_assets_dir, anim_speed=3):
        super().__init__()
        self.rect = rect
        self.static_assets_dir = static_assets_dir
        self.anim_assets_dir = anim_assets_dir

        self.portrait_path = os.path.join(static_assets_dir, "p1_portrait_sheet.png")
        self.frame_path = os.path.join(static_assets_dir, "p1_portrait_frame.png")
        self.shield_crush_path = os.path.join(anim_assets_dir, "shield_crush_anim_6f.png")

        ResourceManager.add_to_cache_static(static_assets_dir)
        ResourceManager.add_to_cache_anim(anim_assets_dir)

        self.portrait_img = ResourceManager.get_static(self.portrait_path)
        self.frame_img = ResourceManager.get_static(self.frame_path)
        self.frame_position = self.frame_img.get_rect(center=self.rect.center).topleft
        self._portrait_offset = (50, 200)
        self.animation_layers = {
            "shield_crush": self.create_animation_layer(
                path=self.shield_crush_path,
                offset=(450, 150),
                speed=anim_speed,
            )
        }

    def update(self, dt):
        for layer in self.animation_layers.values():
            if not layer["frames"] or not layer["playing"]:
                continue

            layer["timer"] += dt
            while layer["timer"] >= layer["speed"]:
                layer["timer"] -= layer["speed"]
                next_frame_index = layer["frame_index"] + 1

                if next_frame_index < len(layer["frames"]):
                    layer["frame_index"] = next_frame_index
                elif layer["loop"]:
                    layer["frame_index"] = 0
                else:
                    layer["frame_index"] = len(layer["frames"]) - 1
                    layer["playing"] = False
                    break

    def draw(self, screen):
        # 1. Рамка задает локальную систему координат для внутренних слоев.
        frame_x, frame_y = self.frame_position

        # Рисуем снизу вверх, потому что последний blit оказывается сверху.
        # 3. Статический портрет: screen -> frame -> portrait.
        portrait_x = frame_x + self._portrait_offset[0]
        portrait_y = frame_y + self._portrait_offset[1]
        screen.blit(self.portrait_img, (portrait_x, portrait_y))

        # 2. Рамка.
        screen.blit(self.frame_img, (frame_x, frame_y))

        # 1. Анимационный слой: screen -> frame -> animation.
        for layer in self.animation_layers.values():
            if not layer["visible"]:
                continue

            frame = layer["frames"][layer["frame_index"]]
            animation_x = frame_x + layer["offset"][0]
            animation_y = frame_y + layer["offset"][1]
            screen.blit(frame, (animation_x, animation_y))

    def set_frame_position(self, x, y):
        self.frame_position = (x, y)

    def get_animation_commands(self, animation_name):
        layer = self.animation_layers.get(animation_name)
        if layer is None:
            raise ValueError(f"Неизвестная анимация: {animation_name}")

        return tuple(sorted(layer["commands"]))

    def send_animation_command(self, animation_name, command, **params):
        layer = self.animation_layers.get(animation_name)
        if layer is None:
            raise ValueError(f"Неизвестная анимация: {animation_name}")

        if command not in layer["commands"]:
            raise ValueError(f"Анимация {animation_name} не поддерживает команду: {command}")

        if command == "play":
            layer["visible"] = True
            layer["playing"] = True
        elif command == "pause":
            layer["playing"] = False
        elif command == "stop":
            layer["playing"] = False
            layer["frame_index"] = 0
            layer["timer"] = 0.0
        elif command == "reset":
            layer["frame_index"] = 0
            layer["timer"] = 0.0
        elif command == "show":
            layer["visible"] = True
        elif command == "hide":
            layer["visible"] = False
        elif command == "set_speed":
            if "speed" not in params:
                raise ValueError("Команда set_speed требует параметр speed")
            layer["speed"] = params["speed"]
        elif command == "set_loop":
            if "loop" not in params:
                raise ValueError("Команда set_loop требует параметр loop")
            layer["loop"] = params["loop"]

    def create_animation_layer(self, path, offset, speed, visible=True, playing=True, loop=True):
        return {
            "frames": ResourceManager.get_animation(path),
            "offset": offset,
            "speed": speed,
            "timer": 0.0,
            "frame_index": 0,
            "visible": visible,
            "playing": playing,
            "loop": loop,
            "commands": set(self.ANIMATION_COMMANDS),
        }


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
