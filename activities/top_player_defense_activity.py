"""Top-seat configuration for the universal player defense Activity."""

from activities.player_defense_activity import PlayerDefenseActivity


class TopPlayerDefenseActivity(PlayerDefenseActivity):
    """Use the shared upright shield frames for the top seat."""

    def __init__(self, overlay_group, frame_duration=0.10):
        super().__init__(overlay_group, frame_duration=frame_duration)
