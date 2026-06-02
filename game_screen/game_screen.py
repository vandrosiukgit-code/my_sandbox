"""Base screen scene for frames, input normalization, and active groups."""

import pygame

from base import BaseGameScreen
from game_screen.frame import Frame
from game_screen.events import ScreenInputEvent, VisualCommand, FrameHit


class GameScreen(BaseGameScreen):
    """Pygame-facing scene.

    GameScreen owns screen frames and visual orchestration. It does not decide
    game rules: raw pygame input is normalized into ScreenInputEvent and sent
    to GameController. Controller responses come back as VisualCommand objects.
    """

    BG_COLOR = (30, 30, 30)
    DOUBLE_CLICK_SECONDS = 0.35
    DOUBLE_CLICK_DISTANCE = 6

    def __init__(self, group_store=None, game_controller=None, background_color=None):
        self.group_store = group_store
        self.game_controller = game_controller
        self.background_color = background_color or self.BG_COLOR
        self.active_group_ids = []
        self.active_activities = []
        self.screen_frames = {}
        self._last_click = None

    def set_group_store(self, group_store):
        self.group_store = group_store

    def set_game_controller(self, game_controller):
        self.game_controller = game_controller

    def create_frame(self, frame_id, rect, hit_rect=None, padding=0, spacing=12, parent_frame_id=None):
        """Create an Frame and register it on this screen."""
        parent_frame = self.get_screen_frame(parent_frame_id) if parent_frame_id else None
        frame = Frame(
            frame_id=frame_id,
            rect=rect,
            hit_rect=hit_rect,
            padding=padding,
            spacing=spacing,
            parent_frame=parent_frame,
        )
        self.add_screen_frame(frame_id, frame)
        if parent_frame is not None:
            parent_frame.add_child_frame(frame)
        return frame

    def add_screen_frame(self, frame_id, frame_config):
        self.screen_frames[frame_id] = frame_config
        return frame_config

    def get_screen_frame(self, frame_id):
        return self.screen_frames[frame_id]

    def put_frame_in_frame(self, child_frame_id, parent_frame_id, position=None):
        """Attach an existing registered frame as a child of another frame."""
        child_frame = self.get_screen_frame(child_frame_id)
        parent_frame = self.get_screen_frame(parent_frame_id)
        if child_frame.parent_frame is not None:
            child_frame.parent_frame.child_frames.pop(child_frame.id, None)
        if position is not None:
            child_frame.set_local_position(*position)
        parent_frame.add_child_frame(child_frame)
        return child_frame

    def put_group_in_frame(self, group_id, frame_id, position=(0, 0)):
        """Put an already active group at a local position inside a frame."""
        group = self.get_group(group_id)
        frame = self.get_screen_frame(frame_id)
        frame.add_group_id(group_id)

        screen_position = frame.to_screen(position)
        group.set_position(*screen_position)
        frame.group_origins[group_id] = screen_position
        return group

    def apply_frame_layout(self, frame_id):
        if self.group_store is None:
            raise RuntimeError("GameScreen.group_store is not connected")
        frame = self.get_screen_frame(frame_id)
        frame.apply_layout(self.group_store)
        return frame

    def activate_group(self, group_id):
        if group_id not in self.active_group_ids:
            self.active_group_ids.append(group_id)
        return self.get_group(group_id)

    def deactivate_group(self, group_id):
        if group_id in self.active_group_ids:
            self.active_group_ids.remove(group_id)

    def get_group(self, group_id):
        if self.group_store is None:
            raise RuntimeError("GameScreen.group_store is not connected")
        return self.group_store.get(group_id)

    def iter_active_groups(self):
        for group_id in self.active_group_ids:
            yield self.get_group(group_id)

    def add_activity(self, activity):
        self.active_activities.append(activity)
        if hasattr(activity, "start"):
            activity.start()
        return activity

    def handle_event(self, event):
        """Normalize pygame input and forward it to GameController."""
        input_event = self.build_input_event(event)
        if input_event is None:
            return True

        visual_commands = self.forward_input_to_controller(input_event)
        self.dispatch_visual_commands(visual_commands)
        return True

    def build_input_event(self, event):
        """Convert a pygame event to a ScreenInputEvent when it matters."""
        if event.type != pygame.MOUSEBUTTONDOWN:
            return None

        button = self.normalize_mouse_button(event.button)
        hit = self.hit_test(event.pos)
        click_type = self.resolve_click_type(button, hit, event.pos)
        return ScreenInputEvent(
            type=click_type,
            button=button,
            group_id=hit.group_id if hit else None,
            frame_id=hit.frame_id if hit else None,
            screen_pos=tuple(event.pos),
            local_pos=hit.local_pos if hit else None,
            raw_event=event,
        )

    def normalize_mouse_button(self, button):
        return {
            1: "left",
            2: "middle",
            3: "right",
            4: "wheel_up",
            5: "wheel_down",
        }.get(button, str(button))

    def resolve_click_type(self, button, hit, screen_pos):
        """Detect double-click as input syntax, not as game meaning."""
        now = pygame.time.get_ticks() / 1000.0
        signature = (
            button,
            hit.frame_id if hit else None,
            hit.group_id if hit else None,
        )
        last_signature, last_time, last_pos = self._last_click or (None, 0.0, None)
        self._last_click = (signature, now, tuple(screen_pos))

        if (
            last_signature == signature
            and self.is_close_click(last_pos, screen_pos)
            and now - last_time <= self.DOUBLE_CLICK_SECONDS
        ):
            return "double_click"
        return "click"

    def is_close_click(self, previous_pos, current_pos):
        """Allow tiny mouse movement between clicks."""
        if previous_pos is None:
            return False
        return (
            abs(previous_pos[0] - current_pos[0]) <= self.DOUBLE_CLICK_DISTANCE
            and abs(previous_pos[1] - current_pos[1]) <= self.DOUBLE_CLICK_DISTANCE
        )

    def hit_test(self, screen_pos):
        """Find the topmost active frame/group at screen_pos."""
        if self.group_store is None:
            return FrameHit(None, None, tuple(screen_pos), None)

        for frame in reversed(tuple(self.iter_root_frames())):
            if hasattr(frame, "hit_test"):
                hit = frame.hit_test(screen_pos, self.group_store)
                if hit is not None:
                    return hit

        for group_id in reversed(self.active_group_ids):
            group = self.get_group(group_id)
            if group.hit_rect.collidepoint(screen_pos):
                return FrameHit(None, group_id, tuple(screen_pos), None)

        return FrameHit(None, None, tuple(screen_pos), None)

    def forward_input_to_controller(self, input_event):
        """Send normalized input to GameController and return visual commands."""
        if self.game_controller is None:
            return ()

        if hasattr(self.game_controller, "handle_input"):
            return self.game_controller.handle_input(input_event) or ()

        if input_event.group_id and hasattr(self.game_controller, "on_group_clicked"):
            self.game_controller.on_group_clicked(input_event.group_id)
        return ()

    def dispatch_visual_commands(self, visual_commands):
        for command in visual_commands or ():
            self.dispatch_visual_command(command)

    def dispatch_visual_command(self, command):
        """Handle simple built-in visual commands.

        Concrete screens can override this method and create domain-specific
        Action objects, for example PlayCardAction.
        """
        command_type = self.get_command_value(command, "type")
        group_id = self.get_command_value(command, "group_id")

        if command_type == "activate_group" and group_id:
            self.activate_group(group_id)
        elif command_type == "deactivate_group" and group_id:
            self.deactivate_group(group_id)

    @staticmethod
    def get_command_value(command, key, default=None):
        if isinstance(command, VisualCommand):
            return getattr(command, key, default)
        if isinstance(command, dict):
            return command.get(key, default)
        return getattr(command, key, default)

    def update(self, dt):
        self.update_screen_frames(dt)
        self.update_activities(dt)

        for group in self.iter_active_groups():
            group.update(dt)

    def update_screen_frames(self, dt):
        for frame in self.iter_root_frames():
            if hasattr(frame, "update_actions"):
                frame.update_actions(dt)

    def iter_root_frames(self):
        for frame in self.screen_frames.values():
            if getattr(frame, "parent_frame", None) is None:
                yield frame

    def update_activities(self, dt):
        running_activities = []
        for activity in self.active_activities:
            activity.update(dt)
            if not self.is_activity_finished(activity):
                running_activities.append(activity)
        self.active_activities = running_activities

    @staticmethod
    def is_activity_finished(activity):
        is_finished = getattr(activity, "is_finished", False)
        if callable(is_finished):
            return is_finished()
        return bool(is_finished)

    def draw(self, screen):
        screen.fill(self.background_color)
        for group in self.iter_active_groups():
            group.draw(screen)


