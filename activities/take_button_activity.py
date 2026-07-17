"""Visual state owner for a configured action button group."""

import pygame

from actions import TakeButtonPressAction
from activities.base_activity import Activity


class TakeButtonActivity(Activity):
    """Manage one action button visuals and clickability inside the screen layer."""

    DIM_MULTIPLIER = 150

    def __init__(
        self,
        button_group,
        button_group_id="btn_take",
        enabled=False,
        enabled_scale=1.0,
        disabled_scale=0.96,
        pressed_scale=0.9,
        press_duration=0.12,
    ):
        super().__init__(group_ids=(button_group_id,), duration=0.0)
        self.button_group = button_group
        self.button_group_id = button_group_id
        self.enabled_scale = float(enabled_scale)
        self.disabled_scale = float(disabled_scale)
        self.pressed_scale = float(pressed_scale)
        self.press_duration = max(0.0, float(press_duration))
        self.enabled_frames = tuple(button_group.get_primary_layer_frames())
        self.disabled_frames = tuple(self.build_disabled_frame(frame) for frame in self.enabled_frames)
        self.enabled = bool(enabled)
        self.locked = False
        self.current_action = None

    def start(self):
        if self.started:
            return
        super().start()
        self.apply_visual_state()

    def update(self, dt):
        if not self.started:
            self.start()
        if self.current_action is None:
            return
        self.current_action.update(dt)
        if self.current_action.is_finished():
            self.current_action = None
            self.apply_visual_state()

    def is_finished(self):
        return False

    def handle_input(self, input_event):
        if getattr(input_event, "group_id", None) != self.button_group_id:
            return True
        if getattr(input_event, "type", None) != "click":
            return True
        if getattr(input_event, "button", None) != "left":
            return True
        if not self.enabled or self.locked:
            return False
        self.locked = True
        self.current_action = TakeButtonPressAction(
            self.button_group,
            base_scale=self.enabled_scale,
            pressed_scale=self.pressed_scale,
            duration=self.press_duration,
        )
        self.current_action.start()
        return True

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self.locked = False
        self.current_action = None
        self.apply_visual_state()
        return self.enabled

    def apply_fixture(self, fixture):
        if not isinstance(fixture, dict):
            return
        if "enabled" in fixture:
            self.set_enabled(bool(fixture["enabled"]))

    def apply_visual_state(self):
        is_interactive = self.enabled and not self.locked
        self.button_group.set_primary_layer_frames(
            self.enabled_frames if is_interactive else self.disabled_frames
        )
        self.button_group.set_scale_factor(
            self.enabled_scale if is_interactive else self.disabled_scale
        )

    @classmethod
    def build_disabled_frame(cls, frame):
        disabled = frame.copy()
        disabled.fill(
            (cls.DIM_MULTIPLIER, cls.DIM_MULTIPLIER, cls.DIM_MULTIPLIER, 255),
            special_flags=pygame.BLEND_RGBA_MULT,
        )
        return disabled
