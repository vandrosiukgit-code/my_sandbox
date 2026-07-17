"""Left-seat configuration for the universal player defense Activity."""

from activities.player_defense_activity import PlayerDefenseActivity


class LeftPlayerDefenseActivity(PlayerDefenseActivity):
    """Use the shared upright shield frames for the left seat."""

    def __init__(self, overlay_group, frame_duration=0.10):
        super().__init__(overlay_group, frame_duration=frame_duration)
