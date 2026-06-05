"""Action that moves one Group to a screen position."""

from actions.base_action import Action
from animations.move_group_animation import MoveGroupAnimation


class MoveGroupAction(Action):
    """Frame-owned visual process for moving a Group."""

    def __init__(self, group, to_position, duration=0.25, from_position=None):
        self.group = group
        super().__init__(
            group_ids=(group.id,),
            animations=(
                MoveGroupAnimation(
                    group=group,
                    from_position=from_position,
                    to_position=to_position,
                    duration=duration,
                ),
            ),
        )
