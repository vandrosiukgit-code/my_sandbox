"""Right-seat configuration for the universal player attack Activity."""

from activities.player_attack_activity import PlayerAttackActivity


class RightPlayerAttackActivity(PlayerAttackActivity):
    """Rotate the shared attack frames toward the table from the right seat."""

    def __init__(self, overlay_group, frame_duration=0.045):
        super().__init__(
            overlay_group,
            frame_duration=frame_duration,
            rotation_degrees=90,
        )
