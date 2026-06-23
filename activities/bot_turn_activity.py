"""Visual activity for orchestrating a bot turn animation sequence."""

from actions import BotCardPlayAction, CardSelectionAction, PlayerCardPlayAction
from activities.base_activity import Activity


class BotTurnActivity(Activity):
    """Dev visual mode that stress-tests bot card movement actions.

    This activity does not decide game rules. It receives GUI-level IDs and
    runs a deterministic visual script: for each bot hand, place first cards
    into every target slot, then second cards into every target slot.
    """

    SLOT_CARD_POSITIONS = ("first", "second")
    BOT_SELECTION_DURATION = 0.08
    BOT_SELECTION_SCALE_MULTIPLIER = 1.04
    BOT_SELECTION_LIFT_PIXELS = 6

    def __init__(
        self,
        bot_hand_ids=None,
        target_slot_ids=None,
        get_activity=None,
        get_frame=None,
        duration=0.5145,
        reset_overlay_on_start=True,
        clear_between_bots=True,
        slot_card_positions=None,
        hand_action_types=None,
        bot_card_resource_key=None,
        freeze_slot_layout=None,
        release_slot_layout=None,
    ):
        super().__init__(duration=0.0)
        self.bot_hand_ids = tuple(bot_hand_ids or ())
        self.target_slot_ids = tuple(target_slot_ids or ())
        self.get_activity = get_activity
        self.get_frame = get_frame
        self.action_duration = max(0.0, float(duration))
        self.reset_overlay_on_start = bool(reset_overlay_on_start)
        self.clear_between_bots = bool(clear_between_bots)
        self.slot_card_positions = tuple(slot_card_positions or self.SLOT_CARD_POSITIONS)
        self.hand_action_types = dict(hand_action_types or {})
        self.bot_card_resource_key = bot_card_resource_key
        self.freeze_slot_layout = freeze_slot_layout
        self.release_slot_layout = release_slot_layout
        self.slot_layout_frozen = False
        self.pending_steps = []
        self.current_action = None
        self.current_step = None
        self.current_phase = None
        self.flight_groups = []
        self.pending_source_removals = []
        self.next_flight_group_index = 0

    def start(self):
        super().start()
        if callable(self.freeze_slot_layout):
            self.freeze_slot_layout()
            self.slot_layout_frozen = True
        try:
            self.pending_steps = self.build_steps()
            self.current_action = None
            self.current_step = None
            self.current_phase = None
            self.flight_groups = []
            self.pending_source_removals = []
            self.next_flight_group_index = 0
            self.start_next_step()
        except Exception:
            self.finish()
            raise

    def update(self, dt):
        if self._finished:
            return
        if not self.started:
            self.start()
            return

        if self.current_action is None and self.pending_source_removals:
            self.flush_pending_source_removals()

        if self.current_action is not None:
            self.current_action.update(dt)
            if not self._is_finished(self.current_action):
                return
            finished_step = self.current_step
            finished_phase = self.current_phase
            self.current_action = None
            if finished_phase == "select":
                action = self.create_flight_action_for_step(finished_step)
                if action is not None:
                    self.current_action = action
                    self.current_phase = "flight"
                    self.current_action.start()
                    return
            self.current_step = None
            self.current_phase = None
            if finished_phase == "flight":
                return

        self.start_next_step()

    def build_steps(self):
        steps = []
        for bot_index, bot_hand_id in enumerate(self.bot_hand_ids):
            if self.should_reset_overlay_before_bot(bot_index):
                steps.append({"type": "reset_table_overlay", "bot_hand_id": bot_hand_id})
            for slot_card_position in self.slot_card_positions:
                for target_slot_id in self.target_slot_ids:
                    steps.append(
                        {
                            "type": "move_card",
                            "bot_hand_id": bot_hand_id,
                            "target_slot_id": target_slot_id,
                            "slot_card_position": slot_card_position,
                        }
                    )
        return steps

    def should_reset_overlay_before_bot(self, bot_index):
        if not self.reset_overlay_on_start:
            return False
        return bot_index == 0 or self.clear_between_bots

    def start_next_step(self):
        while self.pending_steps:
            step = self.pending_steps.pop(0)
            if step["type"] == "reset_table_overlay":
                self.reset_table_overlay()
                continue

            action = self.create_selection_action_for_step(step)
            phase = "select"
            if action is None:
                action = self.create_flight_action_for_step(step)
                phase = "flight"
            if action is None:
                continue

            self.current_step = step
            self.current_phase = phase
            self.current_action = action
            self.current_action.start()
            return action

        self.finish()
        return None

    def reset_table_overlay(self):
        play_area_slots_activity = self.resolve_play_area_slots_activity()
        if play_area_slots_activity is not None and hasattr(play_area_slots_activity, "clear_slot_cards"):
            play_area_slots_activity.clear_slot_cards()
            return
        self.hide_table_slot_cards()

    def create_selection_action_for_step(self, step):
        if self.get_card_play_action_class(step["bot_hand_id"]) is not BotCardPlayAction:
            return None
        hand_activity = self.resolve_activity(step["bot_hand_id"])
        if hand_activity is None:
            return None
        generated_groups = self.get_activity_generated_groups(hand_activity)
        if not generated_groups:
            return None

        target_center = self.resolve_slot_screen_center(step["target_slot_id"])
        source_group = self.select_source_group_for_target(
            hand_activity,
            generated_groups,
            target_center,
        )
        step["_source_group"] = source_group
        to_position, to_scale = self.calculate_bot_selection_target(hand_activity, source_group)
        return CardSelectionAction(
            source_group,
            to_position=to_position,
            to_scale=to_scale,
            duration=self.BOT_SELECTION_DURATION,
        )

    def create_flight_action_for_step(self, step):
        hand_activity = self.resolve_activity(step["bot_hand_id"])
        target_frame = self.resolve_frame(step["target_slot_id"])
        if hand_activity is None or target_frame is None:
            return None
        generated_groups = self.get_activity_generated_groups(hand_activity)
        if not generated_groups:
            return None

        source_group = step.get("_source_group")
        if source_group not in generated_groups:
            source_group = self.select_source_group_for_target(
                hand_activity,
                generated_groups,
                self.resolve_slot_screen_center(step["target_slot_id"]),
            )
        source_geometry = self.get_group_card_screen_geometry(hand_activity, source_group)
        slot_card_index = self.get_slot_card_position_index(step["slot_card_position"])
        back_resource_key, face_resource_key = self.resolve_card_flight_resource_keys(
            hand_activity,
            source_group,
            step["target_slot_id"],
            slot_card_index,
        )
        target_geometry = self.resolve_slot_card_screen_geometry(
            step["target_slot_id"],
            step["slot_card_position"],
            fallback_geometry=source_geometry,
            resource_key=face_resource_key,
        )
        group_id = self.get_next_flight_group_id()
        action_class = self.get_card_play_action_class(step["bot_hand_id"])
        action_kwargs = dict(
            from_geometry=source_geometry,
            to_geometry=target_geometry,
            group_id=group_id,
            duration=self.action_duration,
            cleanup_group=lambda group: self.land_flight_group(
                group,
                step["bot_hand_id"],
                source_group,
                step["target_slot_id"],
                slot_card_index,
                face_resource_key,
            ),
        )
        if action_class is BotCardPlayAction:
            action_kwargs["back_resource_key"] = back_resource_key
            action_kwargs["face_resource_key"] = face_resource_key
        action = action_class(**action_kwargs)
        self.flight_groups.append(action.group)
        return action

    def select_source_group_for_target(self, hand_activity, generated_groups, target_center):
        if not generated_groups:
            return None
        if target_center is None:
            return generated_groups[-1]

        return min(
            generated_groups,
            key=lambda group: self.calculate_center_distance_squared(
                self.get_group_card_screen_geometry(hand_activity, group)["center"],
                target_center,
            ),
        )

    def resolve_slot_screen_center(self, slot_id):
        slot_frame = self.resolve_frame(slot_id)
        if slot_frame is None or not hasattr(slot_frame, "rect"):
            return None
        return tuple(slot_frame.rect.center)

    @staticmethod
    def calculate_center_distance_squared(source_center, target_center):
        dx = source_center[0] - target_center[0]
        dy = source_center[1] - target_center[1]
        return dx * dx + dy * dy

    def calculate_bot_selection_target(self, hand_activity, group):
        base_position = tuple(group.local_rect.topleft)
        base_scale = 1.0 if group.scale_factor is None else float(group.scale_factor)
        target_scale = base_scale * self.BOT_SELECTION_SCALE_MULTIPLIER
        base_width, base_height = self.calculate_group_scaled_local_size(group, base_scale)
        target_width, target_height = self.calculate_group_scaled_local_size(group, target_scale)
        base_center = (
            base_position[0] + base_width / 2,
            base_position[1] + base_height / 2,
        )
        direction = self.resolve_bot_selection_direction(hand_activity, group, base_center)
        target_center = (
            base_center[0] + direction[0] * self.BOT_SELECTION_LIFT_PIXELS,
            base_center[1] + direction[1] * self.BOT_SELECTION_LIFT_PIXELS,
        )
        return (
            int(round(target_center[0] - target_width / 2)),
            int(round(target_center[1] - target_height / 2)),
        ), target_scale

    @classmethod
    def resolve_bot_selection_direction(cls, hand_activity, group, group_center):
        owner = cls.find_nested_activity_with_method(hand_activity, "get_fan_center")
        frame = getattr(owner, "frame", None)
        if owner is not None and frame is not None and hasattr(frame, "content_rect"):
            fan_center = owner.get_fan_center(frame.content_rect)
            dx = group_center[0] - fan_center[0]
            dy = group_center[1] - fan_center[1]
            length = (dx * dx + dy * dy) ** 0.5
            if length > 0.001:
                return dx / length, dy / length
        return 0.0, -1.0

    @staticmethod
    def calculate_group_scaled_local_size(group, scale):
        return (
            int(round(group.local_rect.width * scale)),
            int(round(group.local_rect.height * scale)),
        )

    def resolve_activity(self, activity_id):
        if not callable(self.get_activity):
            return None
        return self.get_activity(activity_id)

    def resolve_frame(self, frame_id):
        if not callable(self.get_frame):
            return None
        return self.get_frame(frame_id)

    def resolve_play_area_slots_activity(self):
        activity = self.resolve_activity("play_area_frame")
        return getattr(activity, "play_area_slots_activity", activity)

    def get_next_flight_group_id(self):
        self.next_flight_group_index += 1
        return f"bot_turn.flight_card.{self.next_flight_group_index}"

    def get_card_play_action_class(self, hand_id):
        action_type = self.hand_action_types.get(hand_id) or self.infer_hand_action_type(hand_id)
        if action_type == "player":
            return PlayerCardPlayAction
        return BotCardPlayAction

    @staticmethod
    def infer_hand_action_type(hand_id):
        if hand_id == "bottom_player_hand":
            return "player"
        return "bot"

    def resolve_card_flight_resource_keys(self, hand_activity, source_group, slot_id, slot_card_index):
        back_resource_key = self.resolve_group_resource_key(hand_activity, source_group)
        face_resource_key = self.bot_card_resource_key or self.resolve_slot_card_resource_key(slot_id, slot_card_index)
        return back_resource_key, face_resource_key or back_resource_key

    def resolve_slot_card_resource_key(self, slot_id, slot_card_index):
        slot_activity = self.resolve_activity(slot_id)
        if slot_activity is None:
            return None
        getter = getattr(slot_activity, "get_card_resource_key_for_index", None)
        if callable(getter):
            try:
                return getter(slot_card_index)
            except (IndexError, RuntimeError):
                return None
        resource_keys = getattr(slot_activity, "card_resource_keys", None)
        if resource_keys is not None and 0 <= slot_card_index < len(resource_keys):
            return resource_keys[slot_card_index]
        return None

    @staticmethod
    def resolve_group_resource_key(activity, group):
        owner = BotTurnActivity.find_nested_activity_with_method(activity, "get_card_selection_context")
        if owner is not None:
            context = owner.get_card_selection_context(group)
            if context is not None and context.get("resource_key"):
                return context["resource_key"]
        owner = BotTurnActivity.find_nested_activity_with_method(activity, "get_card_resource_key")
        if owner is not None:
            hand_index = getattr(owner, "group_hand_indices", {}).get(group.id)
            if hand_index is not None:
                return owner.get_card_resource_key(hand_index)
        raise RuntimeError(f"Cannot resolve resource key for group: {getattr(group, 'id', group)!r}")

    def hide_table_slot_cards(self):
        for target_slot_id in self.target_slot_ids:
            slot_activity = self.resolve_activity(target_slot_id)
            if slot_activity is not None and hasattr(slot_activity, "set_all_card_visual_states"):
                slot_activity.set_all_card_visual_states("hidden")

    def land_flight_group(self, group, bot_hand_id, source_group, slot_id, slot_card_index, resource_key):
        self.remove_flight_group(group)
        self.pending_source_removals.append((bot_hand_id, source_group))
        play_area_slots_activity = self.resolve_play_area_slots_activity()
        if play_area_slots_activity is not None and hasattr(play_area_slots_activity, "place_player_card"):
            play_area_slots_activity.place_player_card(
                {
                    "resource_key": resource_key,
                    "target_slot_id": slot_id,
                }
            )
            return
        slot_activity = self.resolve_activity(slot_id)
        if slot_activity is not None and hasattr(slot_activity, "set_card_visual_state"):
            slot_activity.set_card_visual_state(slot_card_index, "visible")

    def flush_pending_source_removals(self):
        pending_source_removals = self.pending_source_removals
        self.pending_source_removals = []
        for bot_hand_id, source_group in pending_source_removals:
            self.remove_source_card_from_bot_hand(bot_hand_id, source_group)

    def remove_source_card_from_bot_hand(self, bot_hand_id, source_group):
        hand_activity = self.resolve_activity(bot_hand_id)
        owner = self.find_nested_activity_with_method(hand_activity, "remove_generated_group")
        if owner is not None:
            owner.remove_generated_group(source_group)

    def remove_flight_group(self, group):
        self.flight_groups = [flight_group for flight_group in self.flight_groups if flight_group is not group]

    def iter_generated_groups(self):
        return tuple(self.flight_groups)

    def finish(self):
        try:
            if self.current_action is not None and not self._is_finished(self.current_action):
                if hasattr(self.current_action, "cancel"):
                    self.current_action.cancel()
            self.current_action = None
            self.current_step = None
            self.current_phase = None
            self.pending_steps = []
            self.flight_groups = []
            self.pending_source_removals = []
        finally:
            if self.slot_layout_frozen and callable(self.release_slot_layout):
                self.release_slot_layout()
            self.slot_layout_frozen = False
            super().finish()

    def resolve_slot_card_screen_geometry(
        self,
        slot_id,
        slot_card_position,
        fallback_geometry=None,
        resource_key=None,
    ):
        play_area_slots_activity = self.resolve_play_area_slots_activity()
        if play_area_slots_activity is not None and hasattr(play_area_slots_activity, "get_player_turn_target_screen_geometry"):
            geometry = play_area_slots_activity.get_player_turn_target_screen_geometry(
                {
                    "resource_key": resource_key,
                    "target_slot_id": slot_id,
                }
            )
            if geometry is not None:
                return geometry

        slot_activity = self.resolve_activity(slot_id)
        index = self.get_slot_card_position_index(slot_card_position)
        if slot_activity is not None and hasattr(slot_activity, "get_card_screen_geometry"):
            try:
                return slot_activity.get_card_screen_geometry(index)
            except IndexError:
                pass
        if slot_activity is not None and hasattr(slot_activity, "iter_generated_groups"):
            groups = tuple(slot_activity.iter_generated_groups())
            if 0 <= index < len(groups):
                target_group = groups[index]
                return self.get_group_card_screen_geometry(slot_activity, target_group)

        return fallback_geometry

    @staticmethod
    def get_group_card_screen_geometry(activity, group):
        owner = BotTurnActivity.find_nested_activity_with_method(activity, "get_group_card_screen_geometry")
        getter = getattr(owner, "get_group_card_screen_geometry", None)
        if callable(getter):
            return getter(group)
        rect = group.rect.copy()
        return {
            "center": tuple(rect.center),
            "size": tuple(rect.size),
            "angle_degrees": 0.0,
        }

    @staticmethod
    def get_activity_generated_groups(activity):
        if activity is None:
            return ()
        if hasattr(activity, "iter_generated_groups"):
            return tuple(activity.iter_generated_groups())
        return tuple(getattr(activity, "generated_groups", ()))

    @staticmethod
    def find_nested_activity_with_method(activity, method_name):
        while activity is not None:
            if callable(getattr(activity, method_name, None)):
                return activity
            activity = getattr(activity, "hand_activity", None)
        return None

    @staticmethod
    def get_slot_card_position_index(slot_card_position):
        if slot_card_position == "second" or slot_card_position == 1:
            return 1
        return 0

    @staticmethod
    def _is_finished(action):
        is_finished = getattr(action, "is_finished", False)
        if callable(is_finished):
            return is_finished()
        return bool(is_finished)
