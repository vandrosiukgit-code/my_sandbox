"""Base screen scene for zones, input normalization, and active actors."""

import pygame

from base import BaseGameScreen
from game_screen.active_zone import ActiveZone
from game_screen.events import ScreenInputEvent, VisualCommand, ZoneHit


class GameScreen(BaseGameScreen):
    """Pygame-facing scene.

    GameScreen owns screen zones and visual orchestration. It does not decide
    game rules: raw pygame input is normalized into ScreenInputEvent and sent
    to GameController. Controller responses come back as VisualCommand objects.
    """

    BG_COLOR = (30, 30, 30)
    DOUBLE_CLICK_SECONDS = 0.35
    DOUBLE_CLICK_DISTANCE = 6

    def __init__(self, actor_store=None, game_controller=None, background_color=None):
        self.actor_store = actor_store
        self.game_controller = game_controller
        self.background_color = background_color or self.BG_COLOR
        self.active_actor_ids = []
        self.active_activities = []
        self.screen_zones = {}
        self._last_click = None

    def set_actor_store(self, actor_store):
        self.actor_store = actor_store

    def set_game_controller(self, game_controller):
        self.game_controller = game_controller

    def create_zone(self, zone_id, rect, hit_rect=None, padding=0, spacing=12, parent_zone_id=None):
        """Create an ActiveZone and register it on this screen."""
        parent_zone = self.get_screen_zone(parent_zone_id) if parent_zone_id else None
        zone = ActiveZone(
            zone_id=zone_id,
            rect=rect,
            hit_rect=hit_rect,
            padding=padding,
            spacing=spacing,
            parent_zone=parent_zone,
        )
        self.add_screen_zone(zone_id, zone)
        if parent_zone is not None:
            parent_zone.add_child_zone(zone)
        return zone

    def add_screen_zone(self, zone_id, zone_config):
        self.screen_zones[zone_id] = zone_config
        return zone_config

    def get_screen_zone(self, zone_id):
        return self.screen_zones[zone_id]

    def put_zone_in_zone(self, child_zone_id, parent_zone_id, position=None):
        """Attach an existing registered zone as a child of another zone."""
        child_zone = self.get_screen_zone(child_zone_id)
        parent_zone = self.get_screen_zone(parent_zone_id)
        if child_zone.parent_zone is not None:
            child_zone.parent_zone.child_zones.pop(child_zone.id, None)
        if position is not None:
            child_zone.set_local_position(*position)
        parent_zone.add_child_zone(child_zone)
        return child_zone

    def put_actor_in_zone(self, actor_id, zone_id, position=(0, 0)):
        """Put an already active actor at a local position inside a zone."""
        actor = self.get_actor(actor_id)
        zone = self.get_screen_zone(zone_id)
        zone.add_actor_id(actor_id)

        screen_position = zone.to_screen(position)
        actor.set_position(*screen_position)
        zone.actor_origins[actor_id] = screen_position
        return actor

    def apply_zone_layout(self, zone_id):
        if self.actor_store is None:
            raise RuntimeError("GameScreen.actor_store is not connected")
        zone = self.get_screen_zone(zone_id)
        zone.apply_layout(self.actor_store)
        return zone

    def activate_actor(self, actor_id):
        if actor_id not in self.active_actor_ids:
            self.active_actor_ids.append(actor_id)
        return self.get_actor(actor_id)

    def deactivate_actor(self, actor_id):
        if actor_id in self.active_actor_ids:
            self.active_actor_ids.remove(actor_id)

    def get_actor(self, actor_id):
        if self.actor_store is None:
            raise RuntimeError("GameScreen.actor_store is not connected")
        return self.actor_store.get(actor_id)

    def iter_active_actors(self):
        for actor_id in self.active_actor_ids:
            yield self.get_actor(actor_id)

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
            actor_id=hit.actor_id if hit else None,
            zone_id=hit.zone_id if hit else None,
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
            hit.zone_id if hit else None,
            hit.actor_id if hit else None,
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
        """Find the topmost active zone/actor at screen_pos."""
        if self.actor_store is None:
            return ZoneHit(None, None, tuple(screen_pos), None)

        for zone in reversed(tuple(self.iter_root_zones())):
            if hasattr(zone, "hit_test"):
                hit = zone.hit_test(screen_pos, self.actor_store)
                if hit is not None:
                    return hit

        for actor_id in reversed(self.active_actor_ids):
            actor = self.get_actor(actor_id)
            if actor.hit_rect.collidepoint(screen_pos):
                return ZoneHit(None, actor_id, tuple(screen_pos), None)

        return ZoneHit(None, None, tuple(screen_pos), None)

    def forward_input_to_controller(self, input_event):
        """Send normalized input to GameController and return visual commands."""
        if self.game_controller is None:
            return ()

        if hasattr(self.game_controller, "handle_input"):
            return self.game_controller.handle_input(input_event) or ()

        if input_event.actor_id and hasattr(self.game_controller, "on_actor_clicked"):
            self.game_controller.on_actor_clicked(input_event.actor_id)
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
        actor_id = self.get_command_value(command, "actor_id")

        if command_type == "activate_actor" and actor_id:
            self.activate_actor(actor_id)
        elif command_type == "deactivate_actor" and actor_id:
            self.deactivate_actor(actor_id)

    @staticmethod
    def get_command_value(command, key, default=None):
        if isinstance(command, VisualCommand):
            return getattr(command, key, default)
        if isinstance(command, dict):
            return command.get(key, default)
        return getattr(command, key, default)

    def update(self, dt):
        self.update_screen_zones(dt)
        self.update_activities(dt)

        for actor in self.iter_active_actors():
            actor.update(dt)

    def update_screen_zones(self, dt):
        for zone in self.iter_root_zones():
            if hasattr(zone, "update_actions"):
                zone.update_actions(dt)

    def iter_root_zones(self):
        for zone in self.screen_zones.values():
            if getattr(zone, "parent_zone", None) is None:
                yield zone

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
        for actor in self.iter_active_actors():
            actor.draw(screen)
