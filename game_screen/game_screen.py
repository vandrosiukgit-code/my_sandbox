"""Base screen scene for frames, input normalization, and active groups."""

from dataclasses import replace

import pygame

from base import BaseGameScreen
from actions import MoveGroupAction
from game_screen.frame import Frame
from game_screen.events import ActivityResult, ControllerResponse, ScreenInputEvent, VisualCommand, FrameHit
from core.gui_manifest import DEFAULT_GUI_ACTIVITIES, GuiManifest


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
        self.hand_activities = {}
        self.gui_activities = dict(DEFAULT_GUI_ACTIVITIES)
        self._last_click = None

    def set_group_store(self, group_store):
        self.group_store = group_store

    def set_game_controller(self, game_controller):
        self.game_controller = game_controller

    def start(self):
        """Start screen-owned activities that were registered before runtime."""
        for activity in tuple(self.active_activities):
            if hasattr(activity, "start") and not getattr(activity, "started", False):
                activity.start()

    def finish(self):
        """Finish screen-owned activities during runtime shutdown."""
        for activity in tuple(self.active_activities):
            if hasattr(activity, "finish") and not self.is_activity_finished(activity):
                activity.finish()
        self.active_activities = []

    def create_frame(
        self,
        frame_id,
        rect,
        hit_rect=None,
        padding=0,
        spacing=12,
        parent_frame_id=None,
        scale_factor=None,
    ):
        """Create an Frame and register it on this screen."""
        parent_frame = self.get_screen_frame(parent_frame_id) if parent_frame_id else None
        frame = Frame(
            frame_id=frame_id,
            rect=rect,
            hit_rect=hit_rect,
            padding=padding,
            spacing=spacing,
            parent_frame=parent_frame,
            scale_factor=scale_factor,
        )
        self.add_screen_frame(frame_id, frame)
        if parent_frame is not None:
            parent_frame.add_child_frame(frame)
        return frame

    def add_screen_frame(self, frame_id, frame_config):
        self.screen_frames[frame_id] = frame_config
        return frame_config

    def has_screen_frame(self, frame_id):
        return frame_id in self.screen_frames

    def get_screen_frame(self, frame_id):
        return self.screen_frames[frame_id]

    def get_frame_screen_rect(self, frame_id):
        """Return stable screen-space rect for a registered Frame."""
        return self.get_screen_frame(frame_id).rect.copy()

    def get_frame_content_screen_rect(self, frame_id):
        """Return stable screen-space content rect for a registered Frame."""
        frame = self.get_screen_frame(frame_id)
        content_rect = frame.content_rect
        screen_pos = frame.to_screen(content_rect.topleft)
        content_scale = frame.get_content_screen_scale()
        screen_size = (
            max(0, int(round(content_rect.width * content_scale))),
            max(0, int(round(content_rect.height * content_scale))),
        )
        return pygame.Rect(screen_pos, screen_size)

    def get_frame_screen_rects(self, frame_ids):
        """Return stable screen-space rects for registered Frames."""
        return tuple(self.get_frame_screen_rect(frame_id) for frame_id in frame_ids)

    def remove_screen_frame(self, frame_id):
        """Remove a registered frame and detach it from its parent frame."""
        frame = self.screen_frames.pop(frame_id, None)
        if frame is None:
            return None
        if frame.parent_frame is not None:
            frame.parent_frame.remove_child_frame(frame.id)
        return frame

    def put_frame_in_frame(self, child_frame_id, parent_frame_id, position=None):
        """Attach an existing registered frame as a child of another frame."""
        child_frame = self.get_screen_frame(child_frame_id)
        parent_frame = self.get_screen_frame(parent_frame_id)
        if child_frame.parent_frame is not None:
            child_frame.parent_frame.remove_child_frame(child_frame.id)
        if position is not None:
            child_frame.set_local_position(*position)
        parent_frame.add_child_frame(child_frame)
        return child_frame

    def put_group_in_frame(self, group_id, frame_id, position=(0, 0)):
        """Put an already active group at a local position inside a frame."""
        group = self.get_group(group_id)
        frame = self.get_screen_frame(frame_id)
        return frame.place_group_local(group, position)

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

    def is_group_active(self, group_id):
        """Return True when a configured group is active on this screen."""
        return group_id in self.active_group_ids

    def get_group(self, group_id):
        if self.group_store is None:
            raise RuntimeError("GameScreen.group_store is not connected")
        return self.group_store.get(group_id)

    def iter_active_groups(self):
        for group_id in self.active_group_ids:
            yield self.get_group(group_id)

    def add_activity(self, activity):
        if activity not in self.active_activities:
            self.active_activities.append(activity)
        if hasattr(activity, "start"):
            activity.start()
        return activity

    def iter_active_activities(self):
        """Yield active screen-owned activities in draw/update order."""
        return tuple(self.active_activities)

    def remove_activity(self, activity, finish=True):
        """Remove an activity from the screen lifecycle."""
        if finish and hasattr(activity, "finish") and not self.is_activity_finished(activity):
            activity.finish()
        if activity in self.active_activities:
            self.active_activities.remove(activity)
        return activity

    def register_named_activity(self, activity_id, activity):
        """Register an activity under a stable screen-local ID."""
        self.hand_activities[activity_id] = activity
        return activity

    def unregister_named_activity(self, activity_id, finish=True):
        """Unregister a named activity and optionally finish it."""
        activity = self.hand_activities.pop(activity_id, None)
        if activity is not None:
            self.remove_activity(activity, finish=finish)
        return activity

    def get_named_activity(self, activity_id, default=None):
        return self.hand_activities.get(activity_id, default)

    def iter_named_activities(self):
        """Yield stable screen-local activity IDs with their activities."""
        return tuple(self.hand_activities.items())

    def iter_screen_frames(self):
        """Yield screen-owned Frames without exposing their registry for mutation."""
        return tuple(self.screen_frames.values())

    def handle_event(self, event):
        """Normalize pygame input and forward it to GameController."""
        input_event = self.build_input_event(event)
        if input_event is None:
            return True

        input_event = self.enrich_input_event(input_event)

        if self.forward_input_to_activities(input_event) is False:
            return True

        visual_commands = self.forward_input_to_controller(input_event)
        self.dispatch_visual_commands(visual_commands)
        return True

    def build_input_event(self, event):
        """Convert a pygame event to a ScreenInputEvent when it matters."""
        if event.type not in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION):
            return None

        button = self.normalize_mouse_button(event.button) if event.type == pygame.MOUSEBUTTONDOWN else None
        hit = self.hit_test(event.pos)
        click_type = (
            self.resolve_click_type(button, hit, event.pos)
            if event.type == pygame.MOUSEBUTTONDOWN
            else "hover"
        )
        return ScreenInputEvent(
            type=click_type,
            button=button,
            group_id=hit.group_id if hit else None,
            frame_id=hit.frame_id if hit else None,
            screen_pos=tuple(event.pos),
            local_pos=hit.local_pos if hit else None,
            payload={},
            raw_event=event,
        )

    def enrich_input_event(self, input_event):
        """Attach controller-facing visual context from screen activities."""
        payload = dict(input_event.payload or {})
        for activity in reversed(tuple(self.iter_active_activities())):
            context_provider = getattr(activity, "get_input_context", None)
            if context_provider is None:
                continue
            context = context_provider(input_event)
            if context:
                payload.update(context)
        if payload == input_event.payload:
            return input_event
        return replace(input_event, payload=payload)

    def forward_input_to_activities(self, input_event):
        """Let visual activities consume normalized input before controller rules."""
        for activity in reversed(tuple(self.active_activities)):
            handler = getattr(activity, "handle_input", None)
            if handler is not None and handler(input_event) is False:
                return False
        return True

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
            return self.get_controller_response_commands(self.game_controller.handle_input(input_event))

        if input_event.group_id and hasattr(self.game_controller, "on_group_clicked"):
            self.game_controller.on_group_clicked(input_event.group_id)
        return ()

    def forward_activity_result_to_controller(self, result):
        """Send an ActivityResult to GameController and return visual commands."""
        if self.game_controller is None:
            return ()
        if not isinstance(result, ActivityResult):
            raise TypeError("result must be an ActivityResult")
        handler = getattr(self.game_controller, "handle_activity_result", None)
        if handler is None:
            return ()
        return self.get_controller_response_commands(handler(result))

    @staticmethod
    def get_controller_response_commands(response):
        """Normalize legacy command iterables and ControllerResponse objects."""
        if response is None:
            return ()
        if isinstance(response, ControllerResponse):
            return response.commands
        if isinstance(response, VisualCommand):
            return (response,)
        return tuple(response or ())

    def dispatch_visual_commands(self, visual_commands):
        for command in visual_commands or ():
            self.dispatch_visual_command(command)

    def dispatch_visual_command(self, command):
        """Handle simple built-in visual commands.

        Concrete screens can override this method and create domain-specific
        Action objects, for example PlayCardAction.
        """
        command_type = self.get_command_value(command, "type")
        target_id = self.get_command_value(command, "target")
        value = self.get_command_value(command, "value")
        activity_id = self.get_command_value(command, "activity")
        group_id = self.get_command_value(command, "group_id")

        if command_type in ("set_resource", "set_text") and target_id:
            target = self.get_gui_manifest().get_target(target_id)
            self.group_store.apply_target_value(target, value)
        elif command_type == "start_activity" and activity_id:
            self.dispatch_manifest_activity(activity_id, command)
        elif command_type == "move_group" and group_id:
            self.dispatch_move_group_command(command, group_id)
        elif command_type == "activate_group" and group_id:
            self.activate_group(group_id)
        elif command_type == "deactivate_group" and group_id:
            self.deactivate_group(group_id)

    def dispatch_move_group_command(self, command, group_id):
        """Create a frame-owned action that moves one active group."""
        payload = self.get_command_value(command, "payload", {}) or {}
        to_position = self.resolve_move_target_position(command, payload)
        duration = payload.get("duration", self.get_command_value(command, "duration", 0.25))
        frame_id = payload.get("frame_id", self.get_command_value(command, "frame_id"))
        frame = self.get_screen_frame(frame_id) if frame_id else self.find_frame_for_group(group_id)
        group = self.get_group(group_id)
        return frame.add_action(MoveGroupAction(group, to_position, duration=duration, frame=frame))

    def resolve_move_target_position(self, command, payload):
        """Resolve a move target to absolute screen coordinates."""
        for key in ("to", "to_position", "screen_pos"):
            if key in payload:
                return self.normalize_position(payload[key])

        frame_id = payload.get("frame_id", self.get_command_value(command, "frame_id"))
        local_pos = payload.get("local_pos")
        if frame_id and local_pos is not None:
            return self.get_screen_frame(frame_id).to_screen(self.normalize_position(local_pos))

        raise ValueError("move_group command requires payload.to or payload.frame_id + payload.local_pos")

    def find_frame_for_group(self, group_id):
        """Return the first frame that currently owns group_id."""
        for frame in self.screen_frames.values():
            if group_id in frame.group_ids:
                return frame
        raise KeyError(f"Group is not placed in any frame: {group_id}")

    @staticmethod
    def normalize_position(position):
        return int(round(float(position[0]))), int(round(float(position[1])))

    def dispatch_manifest_activity(self, activity_id, command):
        """Dispatch a public manifest activity term.

        Current built-ins only map target groups to active/inactive state.
        Concrete screens can override this to instantiate real Activity classes.
        """
        manifest = self.get_gui_manifest()
        manifest.get_activity(activity_id)
        target_id = self.get_command_value(command, "target")
        target = manifest.get_target(target_id) if target_id else None

        if activity_id == "group.activate" and target and target.group_id:
            self.activate_group(target.group_id)
        elif activity_id == "group.deactivate" and target and target.group_id:
            self.deactivate_group(target.group_id)

    def get_gui_manifest(self):
        """Return public GUI terms available to controller/settings code."""
        targets = self.group_store.get_manifest_targets() if self.group_store else {}
        return GuiManifest(
            targets=targets,
            frames=self.get_manifest_frames(),
            activities=self.gui_activities,
        )

    def get_manifest_frames(self):
        """Return public frame data without exposing group layer internals."""
        return {
            frame_id: {
                "id": frame_id,
                "parent_frame_id": frame.parent_frame.id if frame.parent_frame else None,
                "group_ids": tuple(frame.group_ids),
                "scale_factor": frame.scale_factor,
                "content_screen_scale": frame.get_content_screen_scale(),
            }
            for frame_id, frame in self.screen_frames.items()
        }

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
        for activity in self.active_activities:
            if hasattr(activity, "draw"):
                activity.draw(screen)
        for group in self.iter_active_groups():
            group.draw(screen)
        for frame in self.iter_root_frames():
            frame.draw_debug_tree(screen)


