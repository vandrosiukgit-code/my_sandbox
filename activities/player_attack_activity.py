"""Long-lived attack state built on the reusable frame-animation Activity."""

from actions.attack_animation_action import AttackAnimationAction
from activities.frame_animation_activity import FrameAnimationActivity


class PlayerAttackActivity(FrameAnimationActivity):
    """Own one player's attack state and its finite transition Action."""

    LAYER_NAMES = AttackAnimationAction.LAYER_NAMES
    EXPECTED_FRAME_COUNT = AttackAnimationAction.EXPECTED_FRAME_COUNT

    def __init__(
        self,
        overlay_group,
        frame_duration=0.045,
        *,
        overlay_local_position=None,
        rotation_degrees=0.0,
        flip_x=False,
        flip_y=False,
    ):
        super().__init__(
            overlay_group,
            action_class=AttackAnimationAction,
            layer_names=self.LAYER_NAMES,
            expected_frame_count=self.EXPECTED_FRAME_COUNT,
            frame_duration=frame_duration,
            overlay_local_position=overlay_local_position,
            rotation_degrees=rotation_degrees,
            flip_x=flip_x,
            flip_y=flip_y,
        )

    def start_attack(self):
        return self.start_transition()

    def finish_attack(self):
        return self.finish_transition()

    def build_action_options(self):
        if not self._action_transform_pending:
            return {}
        return {
            "rotation_degrees": self.rotation_degrees,
            "flip_x": self.flip_x,
            "flip_y": self.flip_y,
        }
