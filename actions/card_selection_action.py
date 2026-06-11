"""Action for card hover/selection visual feedback."""

from actions.base_action import Action
from animations.card_selection_animation import CardSelectionAnimation


class CardSelectionAction(Action):
    """Finite visual step that moves/scales one card in frame-local space."""

    def __init__(self, group, to_position, to_scale, duration=0.12, from_position=None, from_scale=None):
        self.group = group
        super().__init__(
            group_ids=(group.id,),
            animations=(
                CardSelectionAnimation(
                    group=group,
                    to_position=to_position,
                    to_scale=to_scale,
                    duration=duration,
                    from_position=from_position,
                    from_scale=from_scale,
                ),
            ),
        )
