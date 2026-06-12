"""Screen-space rect animation for a visual-only Group."""

import pygame

from animations.base_animation import Animation
from animations.easing import ease_out_quad, lerp_int


class ScreenRectGroupAnimation(Animation):
    """Animate a visual-only Group from one screen rect to another."""

    animated_properties = ("screen_rect",)
    coordinate_space = "screen"

    def __init__(
        self,
        group,
        to_rect,
        duration=0.25,
        from_rect=None,
        from_surface=None,
        to_surface=None,
        on_finish=None,
    ):
        super().__init__(duration=duration, on_finish=on_finish)
        self.validate_group(group)
        self.group = group
        self.from_rect = self.normalize_rect(from_rect) if from_rect is not None else None
        self.to_rect = self.normalize_rect(to_rect)
        self._initial_from_rect = self.from_rect
        self._explicit_from_rect = from_rect is not None
        self.from_surface = self.normalize_surface(
            from_surface,
            group.get_primary_layer().get_current_frame(),
            "from_surface",
        )
        self.to_surface = self.normalize_optional_surface(to_surface, "to_surface")

    def start(self):
        super().start()
        if not self._explicit_from_rect:
            self.from_rect = self.group.rect.copy()
        self.apply(0.0)

    def reset(self):
        super().reset()
        self.from_rect = self._initial_from_rect

    def apply(self, progress):
        progress = ease_out_quad(progress)
        rect = pygame.Rect(
            lerp_int(self.from_rect.x, self.to_rect.x, progress),
            lerp_int(self.from_rect.y, self.to_rect.y, progress),
            max(1, lerp_int(self.from_rect.width, self.to_rect.width, progress)),
            max(1, lerp_int(self.from_rect.height, self.to_rect.height, progress)),
        )
        self.group.set_rect(rect)
        self.group.set_primary_layer_frames(
            [self.render_surface(rect.size, progress)],
            position=(0, 0),
        )

    def render_surface(self, size, progress):
        from_surface = pygame.transform.smoothscale(self.from_surface, size)
        if self.to_surface is None:
            return from_surface

        to_surface = pygame.transform.smoothscale(self.to_surface, size)
        if progress >= 1.0:
            return to_surface

        blended = from_surface.copy()
        overlay = to_surface.copy()
        overlay.set_alpha(lerp_int(0, 255, progress))
        blended.blit(overlay, (0, 0))
        return blended

    @staticmethod
    def normalize_rect(rect):
        if isinstance(rect, pygame.Rect):
            return rect.copy()
        if not isinstance(rect, (tuple, list)) or len(rect) < 4:
            raise TypeError(f"rect must be a pygame.Rect or 4-item tuple/list: {rect!r}")
        return pygame.Rect(
            int(round(float(rect[0]))),
            int(round(float(rect[1]))),
            max(1, int(round(float(rect[2])))),
            max(1, int(round(float(rect[3])))),
        )

    @classmethod
    def normalize_optional_surface(cls, surface, name):
        if surface is None:
            return None
        return cls.normalize_surface(surface, None, name)

    @staticmethod
    def normalize_surface(surface, default_surface, name):
        if surface is None:
            surface = default_surface
        if surface is None:
            raise ValueError(f"{name} is required")
        if not isinstance(surface, pygame.Surface):
            raise TypeError(f"{name} must be pygame.Surface: {surface!r}")
        return surface.copy()

    @staticmethod
    def validate_group(group):
        required = ("id", "rect", "set_rect", "set_primary_layer_frames", "get_primary_layer")
        missing = [name for name in required if not hasattr(group, name)]
        if missing:
            raise TypeError(f"group is not compatible with ScreenRectGroupAnimation: missing {missing!r}")
