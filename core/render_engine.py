"""Pygame runtime loop for the active game screen.

Contract:
- RenderEngine owns pygame init, display creation, event polling, dt policy,
  screen lifecycle, display flip, and guaranteed pygame shutdown.
- GameScreen owns scene orchestration and must fully redraw the display unless
  RenderEngine is configured with a background_color.
"""

from dataclasses import dataclass
import inspect
import logging
import os
from typing import Protocol

import pygame

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RenderContext:
    """Runtime context passed to screen factories that accept it."""

    display_surface: pygame.Surface
    screen_size: tuple[int, int]
    clock: pygame.time.Clock
    target_fps: int
    max_dt: float
    fixed_size: bool


@dataclass(frozen=True)
class ScreenTransition:
    screen_factory: object
    screen_size: tuple[int, int] | None = None
    title: str | None = None


class GameScreenLike(Protocol):
    """Minimal screen contract used by RenderEngine."""

    def handle_event(self, event) -> object: ...
    def update(self, dt: float) -> None: ...
    def draw(self, surface: pygame.Surface) -> None: ...


class RenderEngine:
    """Small Pygame runner for one active game screen."""

    def __init__(
        self,
        screen_factory,
        screen_size=(800, 600),
        title="Sandbox",
        target_fps=60,
        max_dt=0.1,
        time_scale=1.0,
        display_flags=0,
        vsync=0,
        fixed_size=True,
        background_color=None,
        input_mapper=None,
    ):
        self._apply_window_position_defaults()
        pygame.init()
        self.screen_size = tuple(screen_size)
        self.fixed_size = bool(fixed_size)
        self.display_flags = int(display_flags)
        if not self.fixed_size:
            self.display_flags |= pygame.RESIZABLE
        self.vsync = int(vsync)
        self.screen = pygame.display.set_mode(
            self.screen_size,
            flags=self.display_flags,
            vsync=self.vsync,
        )
        pygame.display.set_caption(title)
        self.clock = pygame.time.Clock()
        self.target_fps = max(1, int(target_fps))
        self.max_dt = max(0.0, float(max_dt))
        self.time_scale = max(0.0, float(time_scale))
        self.background_color = background_color
        self.input_mapper = input_mapper
        self.context = self.build_context()
        self.game_screen = self.create_screen(screen_factory)

    @staticmethod
    def _apply_window_position_defaults():
        if "SDL_VIDEO_WINDOW_POS" in os.environ:
            return
        os.environ.setdefault("SDL_VIDEO_CENTERED", "1")

    def build_context(self):
        return RenderContext(
            display_surface=self.screen,
            screen_size=self.screen_size,
            clock=self.clock,
            target_fps=self.target_fps,
            max_dt=self.max_dt,
            fixed_size=self.fixed_size,
        )

    def create_screen(self, screen_factory):
        """Create a screen, passing RenderContext when the factory accepts it."""
        if self.screen_factory_accepts_context(screen_factory):
            return screen_factory(self.context)
        return screen_factory()

    @staticmethod
    def screen_factory_accepts_context(screen_factory):
        try:
            signature = inspect.signature(screen_factory)
        except (TypeError, ValueError):
            return False
        return any(
            parameter.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.VAR_POSITIONAL,
            )
            for parameter in signature.parameters.values()
        )

    def run(self):
        """Run screen lifecycle and always release pygame resources."""
        try:
            self.start_screen(self.game_screen)
            self._run_loop()
        except Exception:
            logger.exception("RenderEngine failed")
            raise
        finally:
            self.shutdown()

    def _run_loop(self):
        """Run event, update, draw, and display-flip steps."""
        running = True
        while running:
            dt = self.get_frame_dt()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    self.handle_resize(event)
                elif self.should_stop_from_event(event):
                    running = False

            self.game_screen.update(dt)
            if self.background_color is not None:
                self.screen.fill(self.background_color)
            self.game_screen.draw(self.screen)
            pygame.display.flip()

    def get_frame_dt(self):
        raw_dt = self.clock.tick(self.target_fps) / 1000.0
        if self.max_dt > 0:
            raw_dt = min(raw_dt, self.max_dt)
        return raw_dt * self.time_scale

    def should_stop_from_event(self, event):
        """Return True when the screen explicitly requests shutdown."""
        result = self.dispatch_event(event)
        if isinstance(result, ScreenTransition):
            self.apply_screen_transition(result)
            return False
        return result is False or result == "quit"

    def dispatch_event(self, event):
        """Dispatch a pygame event through an optional mapper or the screen."""
        if self.input_mapper is None:
            return self.game_screen.handle_event(event)

        mapped_events = self.input_mapper.map_pygame_event(event)
        result = None
        for input_event in mapped_events or ():
            if hasattr(self.game_screen, "handle_input"):
                result = self.game_screen.handle_input(input_event)
            else:
                result = self.game_screen.handle_event(input_event)
            if result is False or result == "quit":
                return result
        return result

    def handle_resize(self, event):
        """Apply the fixed/resizable window policy."""
        if self.fixed_size:
            return
        self.screen_size = (int(event.w), int(event.h))
        self.screen = pygame.display.set_mode(
            self.screen_size,
            flags=self.display_flags,
            vsync=self.vsync,
        )
        self.context = self.build_context()
        if hasattr(self.game_screen, "resize"):
            self.game_screen.resize(self.screen_size)

    def set_game_screen(self, game_screen):
        """Switch the active screen with lifecycle cleanup."""
        self.finish_screen(self.game_screen)
        self.game_screen = game_screen
        self.start_screen(self.game_screen)

    def apply_screen_transition(self, transition):
        if transition.screen_size is not None and tuple(transition.screen_size) != self.screen_size:
            self.screen_size = tuple(transition.screen_size)
            self.screen = pygame.display.set_mode(
                self.screen_size,
                flags=self.display_flags,
                vsync=self.vsync,
            )
            self.context = self.build_context()
        if transition.title is not None:
            self.set_title(transition.title)
        self.set_game_screen(self.create_screen(transition.screen_factory))

    @staticmethod
    def start_screen(game_screen):
        if hasattr(game_screen, "start"):
            game_screen.start()

    @staticmethod
    def finish_screen(game_screen):
        if hasattr(game_screen, "finish"):
            game_screen.finish()

    def set_title(self, title):
        pygame.display.set_caption(title)

    def set_icon(self, icon_surface):
        pygame.display.set_icon(icon_surface)

    def shutdown(self):
        self.finish_screen(self.game_screen)
        pygame.quit()
