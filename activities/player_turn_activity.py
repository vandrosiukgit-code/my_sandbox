"""High-level activity for one player's turn on the play area."""

from actions import PlayerCardPlayAction
from activities.base_activity import Activity
from activities.generated_groups import GeneratedGroupRegistry


class PlayerTurnActivity(Activity):
    """Own the visual process of a player turn on the play area.

    At this stage the turn activity delegates card-slot placement to
    PlayAreaSlotsActivity. Later it can coordinate turn-level effects,
    controller commands, focus, and short actions without making the table
    screen own those details directly.
    """

    def __init__(
        self,
        play_area_slots_activity,
        owns_play_area_slots_activity=False,
        freeze_slot_layout=None,
        release_slot_layout=None,
        remove_source_card=None,
        on_safe_point=None,
    ):
        super().__init__(duration=0.0)
        self.validate_play_area_slots_activity(play_area_slots_activity)
        self.play_area_slots_activity = play_area_slots_activity
        self.owns_play_area_slots_activity = bool(owns_play_area_slots_activity)
        self.turn_context = None
        self.turn_active = False
        self.current_action = None
        self.flight_group_registry = GeneratedGroupRegistry("player_turn.flight_card")
        self.freeze_slot_layout = freeze_slot_layout
        self.release_slot_layout = release_slot_layout
        self.remove_source_card = remove_source_card
        self.on_safe_point = on_safe_point
        self.slot_layout_frozen = False
        self.slot_layout_release_pending = False
        self.source_card_removed = False
        self.completed_turn_context = None
        self.safe_point_emitted = False

    @property
    def flight_groups(self):
        return self.flight_group_registry.iter_groups()

    @flight_groups.setter
    def flight_groups(self, groups):
        self.flight_group_registry.set_groups(groups)

    @staticmethod
    def validate_play_area_slots_activity(play_area_slots_activity):
        if play_area_slots_activity is None:
            raise ValueError("PlayerTurnActivity requires play_area_slots_activity")
        for method_name in ("start", "update", "finish"):
            if not callable(getattr(play_area_slots_activity, method_name, None)):
                raise TypeError(f"play_area_slots_activity must provide {method_name}()")

    def start(self):
        if self.started:
            return
        super().start()
        if not getattr(self.play_area_slots_activity, "started", False):
            self.play_area_slots_activity.start()

    def start_turn(self, turn_context):
        """Start one visual turn with controller-facing context."""
        if self.turn_active or self.slot_layout_release_pending:
            return False
        if not self.started:
            self.start()
        if callable(self.freeze_slot_layout):
            self.freeze_slot_layout()
            self.slot_layout_frozen = True
        try:
            self.turn_context = self.build_turn_context(turn_context)
            self.current_action = self.create_player_card_action(self.turn_context)
            self.remove_source_card_for_turn()
            if self.current_action is not None:
                self.current_action.start()
            self.turn_active = True
            self.safe_point_emitted = False
            return True
        except Exception:
            self.release_frozen_slot_layout()
            raise

    def create_player_card_action(self, turn_context):
        source_geometry = turn_context.get("source_screen_geometry")
        target_geometry = turn_context.get("target_screen_geometry")
        resource_key = turn_context.get("resource_key") or turn_context.get("card_id")
        if not source_geometry or not target_geometry or not resource_key:
            return None

        action = PlayerCardPlayAction(
            from_geometry=source_geometry,
            to_geometry=target_geometry,
            face_resource_key=resource_key,
            group_id=self.get_next_flight_group_id(),
            cleanup_group=self.remove_flight_group,
        )
        self.flight_group_registry.append(action.group)
        return action

    def remove_source_card_for_turn(self):
        """Remove the source hand card before flight so hand relayout runs with it."""
        if self.source_card_removed:
            return False
        if not callable(self.remove_source_card):
            return False
        self.source_card_removed = bool(self.remove_source_card(self.turn_context))
        return self.source_card_removed

    def get_next_flight_group_id(self):
        return self.flight_group_registry.next_id()

    def build_turn_context(self, turn_context):
        context = dict(turn_context or {})
        context["target_screen_geometry"] = self.resolve_target_screen_geometry(context)
        return context

    def resolve_target_screen_geometry(self, turn_context):
        slot_activity = self.resolve_target_slot_activity(turn_context)
        if slot_activity is None:
            return None
        getter = getattr(slot_activity, "get_player_turn_target_screen_geometry", None)
        if callable(getter):
            return getter(turn_context)
        getter = getattr(slot_activity, "get_card_screen_geometry", None)
        if callable(getter):
            try:
                return getter(0)
            except IndexError:
                return None
        return None

    def resolve_target_slot_activity(self, turn_context):
        if callable(getattr(self.play_area_slots_activity, "place_player_card", None)):
            return self.play_area_slots_activity
        slot_id = turn_context.get("slot_id") or turn_context.get("target_slot_id")
        slot_activities = getattr(self.play_area_slots_activity, "slot_activities", {})
        if slot_id:
            return slot_activities.get(slot_id)
        if slot_activities:
            return next(iter(slot_activities.values()))
        return getattr(self.play_area_slots_activity, "prototype_slot_activity", None)

    def finish_turn(self):
        """Finish the current visual turn without finishing the activity."""
        self.completed_turn_context = dict(self.turn_context or {})
        self.place_turn_card_in_target_slot()
        self.current_action = None
        self.flight_group_registry.clear()
        self.turn_active = False
        self.turn_context = None
        self.source_card_removed = False
        self.slot_layout_release_pending = self.has_pending_slot_transfers()
        if not self.slot_layout_release_pending:
            self.release_frozen_slot_layout()
            self.emit_safe_point()

    def place_turn_card_in_target_slot(self):
        if not self.turn_context:
            return False
        slot_activity = self.resolve_target_slot_activity(self.turn_context)
        placer = getattr(slot_activity, "place_player_card", None)
        if callable(placer):
            return placer(self.turn_context) is not False
        return False

    def update(self, dt):
        if not self.started:
            self.start()
            return
        self.play_area_slots_activity.update(dt)
        if self.slot_layout_release_pending and not self.has_pending_slot_transfers():
            self.slot_layout_release_pending = False
            self.release_frozen_slot_layout()
            self.emit_safe_point()
        if self.current_action is None:
            return
        self.current_action.update(dt)
        if self.current_action.is_finished():
            self.current_action = None
            self.finish_turn()

    def draw(self, screen):
        self.draw_debug_overlay(screen)

    def draw_debug_overlay(self, screen):
        if hasattr(self.play_area_slots_activity, "draw_debug_overlay"):
            self.play_area_slots_activity.draw_debug_overlay(screen)
        elif hasattr(self.play_area_slots_activity, "draw"):
            self.play_area_slots_activity.draw(screen)

    def iter_generated_groups(self):
        groups = list(self.flight_group_registry.iter_groups())
        if hasattr(self.play_area_slots_activity, "iter_generated_groups"):
            groups.extend(self.play_area_slots_activity.iter_generated_groups())
        return tuple(groups)

    def iter_groups_in_draw_order(self):
        groups = []
        group_iterator = getattr(self.play_area_slots_activity, "iter_groups_in_draw_order", None)
        if not callable(group_iterator):
            group_iterator = getattr(self.play_area_slots_activity, "iter_generated_groups", None)
        if callable(group_iterator):
            groups.extend(group_iterator())
        groups.extend(self.flight_group_registry.iter_groups())
        return tuple(groups)

    def remove_flight_group(self, group):
        self.flight_group_registry.remove(group)

    def has_pending_slot_transfers(self):
        checker = getattr(self.play_area_slots_activity, "has_pending_slot_transfers", None)
        return bool(checker()) if callable(checker) else False

    def release_frozen_slot_layout(self):
        if self.slot_layout_frozen and callable(self.release_slot_layout):
            self.release_slot_layout()
        self.slot_layout_frozen = False

    def emit_safe_point(self):
        if self.safe_point_emitted:
            return False
        if not callable(self.on_safe_point):
            return False
        payload = dict(self.completed_turn_context or {})
        payload["safe_point"] = "turn.played.safe_point"
        self.on_safe_point("turn.played.safe_point", payload)
        self.safe_point_emitted = True
        return True

    def apply_fixture(self, fixture):
        if hasattr(self.play_area_slots_activity, "apply_fixture"):
            self.play_area_slots_activity.apply_fixture(fixture)

    def consume_completed_turn_context(self):
        context = self.completed_turn_context
        self.completed_turn_context = None
        return context

    def is_finished(self):
        return self._finished

    def finish(self):
        try:
            if self.owns_play_area_slots_activity:
                is_finished = getattr(self.play_area_slots_activity, "is_finished", None)
                if not callable(is_finished) or not is_finished():
                    self.play_area_slots_activity.finish()
            self.turn_active = False
            self.turn_context = None
            self.current_action = None
            self.source_card_removed = False
            self.completed_turn_context = None
            self.safe_point_emitted = False
            self.flight_group_registry.clear()
            self.slot_layout_release_pending = False
        finally:
            self.release_frozen_slot_layout()
            super().finish()
