"""Visual action for moving one table-slot card to another slot."""

from actions.player_card_play_action import PlayerCardPlayAction


class SlotCardHoverFlightAction(PlayerCardPlayAction):
    """Finite visual step for one card moving between table slots.

    The action owns only the transient flight group. Slot state changes are
    passed in through callbacks owned by the activity that orchestrates slots.
    """

    def __init__(
        self,
        from_geometry,
        to_geometry,
        face_resource_key,
        duration=0.22,
        group_id="slot_card_hover.flight_card",
        cleanup_group=None,
        land_card=None,
        resource_manager=None,
    ):
        self.land_card = land_card
        kwargs = {}
        if resource_manager is not None:
            kwargs["resource_manager"] = resource_manager
        super().__init__(
            from_geometry=from_geometry,
            to_geometry=to_geometry,
            face_resource_key=face_resource_key,
            duration=duration,
            group_id=group_id,
            cleanup_group=cleanup_group,
            **kwargs,
        )

    def finish_player_card_move(self, animation):
        if callable(self.land_card):
            self.land_card()
        super().finish_player_card_move(animation)
