"""Attack specialization of the reusable frame-animation Action."""

import pygame

from actions.frame_animation_action import FrameAnimationAction


class AttackAnimationAction(FrameAnimationAction):
    """Play one attack-overlay frame range without owning persistent state."""

    LAYER_NAMES = ("attack_overlay",)
    EXPECTED_FRAME_COUNT = 13

    def __init__(
        self,
        overlay_group,
        *,
        layer_names=LAYER_NAMES,
        start_frame_index=0,
        target_frame_index,
        frame_duration=0.045,
        rotation_degrees=0.0,
        flip_x=False,
        flip_y=False,
    ):
        self.rotation_degrees = float(rotation_degrees) % 360.0
        self.flip_x = bool(flip_x)
        self.flip_y = bool(flip_y)
        super().__init__(
            overlay_group,
            layer_names=layer_names,
            start_frame_index=start_frame_index,
            target_frame_index=target_frame_index,
            frame_duration=frame_duration,
            expected_frame_count=self.EXPECTED_FRAME_COUNT,
        )
        self.prepare_overlay_frames()

    def prepare_overlay_frames(self):
        if not (self.rotation_degrees or self.flip_x or self.flip_y):
            return
        for layer_name in self.layer_names:
            source_frames = self.overlay_group.get_layer_frames(layer_name)
            transformed_frames = tuple(
                self.transform_frame(frame)
                for frame in source_frames
            )
            source_size = source_frames[0].get_size()
            transformed_size = transformed_frames[0].get_size()
            layer_position = (
                round((source_size[0] - transformed_size[0]) / 2),
                round((source_size[1] - transformed_size[1]) / 2),
            )
            self.overlay_group.set_layer_frames(layer_name, transformed_frames)
            self.overlay_group.set_layer_position(layer_name, layer_position)

    def transform_frame(self, frame):
        transformed = frame
        if self.flip_x or self.flip_y:
            transformed = pygame.transform.flip(transformed, self.flip_x, self.flip_y)
        if self.rotation_degrees:
            transformed = pygame.transform.rotate(transformed, self.rotation_degrees)
        return transformed
