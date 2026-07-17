"""Defense specialization of the reusable frame-animation Action."""

from actions.frame_animation_action import FrameAnimationAction


class DefenseAnimationAction(FrameAnimationAction):
    """Play one shield-overlay transition with the defense frame contract."""

    LAYER_NAMES = ("defense_overlay",)
    EXPECTED_FRAME_COUNT = 8

    def __init__(
        self,
        overlay_group,
        *,
        layer_names=LAYER_NAMES,
        start_frame_index=0,
        target_frame_index,
        frame_duration=0.10,
    ):
        super().__init__(
            overlay_group,
            layer_names=layer_names,
            start_frame_index=start_frame_index,
            target_frame_index=target_frame_index,
            frame_duration=frame_duration,
            expected_frame_count=self.EXPECTED_FRAME_COUNT,
            hold_frame_count=2 if target_frame_index > start_frame_index else 0,
            return_frame_index=0 if target_frame_index > start_frame_index else None,
        )
