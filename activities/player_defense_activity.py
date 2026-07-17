"""Long-lived defense state built on the reusable frame-animation Activity."""

import pygame

from actions.defense_animation_action import DefenseAnimationAction
from activities.frame_animation_activity import FrameAnimationActivity


class PlayerDefenseActivity(FrameAnimationActivity):
    """Own one player's shield state and its finite transition Action."""

    LAYER_NAMES = DefenseAnimationAction.LAYER_NAMES
    EXPECTED_FRAME_COUNT = DefenseAnimationAction.EXPECTED_FRAME_COUNT

    def __init__(
        self,
        overlay_group,
        frame_duration=0.10,
        *,
        overlay_local_position=None,
        rotation_degrees=0.0,
        flip_x=False,
        flip_y=False,
    ):
        super().__init__(
            overlay_group,
            action_class=DefenseAnimationAction,
            layer_names=self.LAYER_NAMES,
            expected_frame_count=self.EXPECTED_FRAME_COUNT,
            frame_duration=frame_duration,
            overlay_local_position=overlay_local_position,
            rotation_degrees=rotation_degrees,
            flip_x=flip_x,
            flip_y=flip_y,
        )

    def start_defense(self):
        return self.begin_transition(
            self.frame_count - 1,
            "entering",
            "idle",
        )

    def finish_defense(self):
        return self.finish_transition()

    def prepare_overlay_frames(self):
        super().prepare_overlay_frames()
        for layer_name in self.LAYER_NAMES:
            frames = list(self.overlay_group.get_layer_frames(layer_name))
            frames[0] = pygame.Surface(frames[0].get_size(), pygame.SRCALPHA)
            self.overlay_group.set_layer_frames(layer_name, frames)
