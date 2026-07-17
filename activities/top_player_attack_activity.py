"""Top-seat configuration for the universal player attack Activity."""

from activities.player_attack_activity import PlayerAttackActivity


class TopPlayerAttackActivity(PlayerAttackActivity):
    """Use the shared attack frames reflected across the horizontal axis."""

    def __init__(self, overlay_group, frame_duration=0.045):
        super().__init__(
            overlay_group,
            frame_duration=frame_duration,
            flip_y=True,
        )
