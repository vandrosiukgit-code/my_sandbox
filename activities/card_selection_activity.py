"""High-level activity for selecting a card from a player hand."""

from activities.base_activity import Activity
from actions import CardSelectionAction


class CardSelectionActivity(Activity):
    """Own the visual process of choosing a card from a hand.

    It watches generated hand-card groups, enlarges the card under the cursor,
    and exposes controller-facing card context for selection input.
    """

    HOVER_SCALE_MULTIPLIER = 1.18
    HOVER_ANIMATION_SECONDS = 0.16
    HOVER_LIFT_PIXELS = 28
    HOVER_HYSTERESIS_PIXELS = 8
    HOVER_EDGE_CARD_HYSTERESIS_PIXELS = 18

    def __init__(self, hand_activity, owns_hand_activity=False):
        super().__init__(duration=0.0)
        self.validate_hand_activity(hand_activity)
        self.hand_activity = hand_activity
        self.owns_hand_activity = bool(owns_hand_activity)
        self.hovered_group = None
        self.selected_card_context = None
        self.selection_actions = {}
        self.rest_states = {}
        self._last_hand_layout_signature = None

    @staticmethod
    def validate_hand_activity(hand_activity):
        if hand_activity is None:
            raise ValueError("CardSelectionActivity requires hand_activity")
        for method_name in ("start", "update", "finish"):
            if not callable(getattr(hand_activity, method_name, None)):
                raise TypeError(f"hand_activity must provide {method_name}()")

    def start(self):
        if self.started:
            return
        super().start()
        if not getattr(self.hand_activity, "started", False):
            self.hand_activity.start()

    def update(self, dt):
        if not self.started:
            self.start()
            return
        self.hand_activity.update(dt)
        self.invalidate_rest_states_if_layout_changed()
        self.prune_stale_group_state()
        self.refresh_rest_states()
        self.update_selection_actions(dt)

    def draw(self, screen):
        self.draw_debug_overlay(screen)

    def draw_debug_overlay(self, screen):
        if hasattr(self.hand_activity, "draw_debug_overlay"):
            self.hand_activity.draw_debug_overlay(screen)
        elif hasattr(self.hand_activity, "draw"):
            self.hand_activity.draw(screen)

    def apply_fixture(self, fixture):
        if hasattr(self.hand_activity, "apply_fixture"):
            self.hand_activity.apply_fixture(fixture)

    def handle_input(self, input_event):
        event_type = getattr(input_event, "type", None)
        if event_type == "hover":
            screen_pos = getattr(input_event, "screen_pos", None)
            if screen_pos is not None:
                self.handle_hover(screen_pos)
            return False
        return True

    def handle_hover(self, screen_pos):
        next_hovered_group = self.find_card_at(screen_pos)
        if next_hovered_group is self.hovered_group:
            return

        self.restore_non_hovered_groups(next_hovered_group)

        self.hovered_group = next_hovered_group
        if self.hovered_group is not None:
            self.ensure_rest_state(self.hovered_group)
            self.animate_group_to_hover(self.hovered_group)

    def select_card_context(self, card_group):
        self.selected_card_context = self.get_card_selection_context(card_group)
        return self.selected_card_context

    def get_input_context(self, input_event):
        """Return controller-facing card context for selection input."""
        if getattr(input_event, "type", None) != "click":
            return {}
        if getattr(input_event, "button", None) != "left":
            return {}
        if self.hovered_group is None:
            return {}
        clicked_group = self.find_card_at(getattr(input_event, "screen_pos", None))
        if clicked_group is not self.hovered_group:
            return {}
        return {"selected_card": self.build_selected_card_intent(clicked_group)}

    def build_selected_card_intent(self, card_group):
        context = dict(self.select_card_context(card_group) or {})
        resource_key = context.get("resource_key") or context.get("card_id")
        rank, suit = self.parse_card_resource_key(resource_key)
        context.update(
            {
                "rank": rank,
                "suit": suit,
                "source_screen_geometry": self.get_card_screen_geometry(card_group),
            }
        )
        return context

    @staticmethod
    def get_card_screen_geometry(group):
        rect = group.rect.copy()
        return {
            "center": tuple(rect.center),
            "size": tuple(rect.size),
            "angle_degrees": 0.0,
        }

    @staticmethod
    def parse_card_resource_key(resource_key):
        if not isinstance(resource_key, str):
            return None, None
        card_name = resource_key.rsplit(".", 1)[-1]
        if "_of_" not in card_name:
            return None, None
        rank, suit = card_name.split("_of_", 1)
        return rank, suit

    def find_selectable_card_at(self, screen_pos):
        if self.hovered_group is not None:
            return self.hovered_group
        if screen_pos is None:
            return None
        return self.find_card_at(screen_pos)

    def get_card_selection_context(self, group):
        if hasattr(self.hand_activity, "get_card_selection_context"):
            context = self.hand_activity.get_card_selection_context(group)
            if context is not None:
                return context
        return {
            "group_id": group.id,
            "card_id": group.id,
            "hand_index": None,
            "resource_key": None,
        }

    def find_card_at(self, screen_pos):
        visible_hit_rects = self.get_visible_hit_rects()
        for index, (group, visible_rect) in enumerate(visible_hit_rects):
            if group is self.hovered_group:
                hysteresis = self.get_hysteresis_pixels(index, len(visible_hit_rects))
                stable_rect = visible_rect.inflate(
                    hysteresis * 2,
                    hysteresis * 2,
                )
                if stable_rect.collidepoint(screen_pos):
                    return group

        for group, visible_rect in visible_hit_rects:
            if visible_rect.collidepoint(screen_pos):
                return group
        return None

    def get_hysteresis_pixels(self, index, count):
        if index <= 2 or index >= count - 3:
            return self.HOVER_EDGE_CARD_HYSTERESIS_PIXELS
        return self.HOVER_HYSTERESIS_PIXELS

    def get_visible_hit_rects(self):
        """Approximate visible card zones after fan overlap.

        Cards in the fan overlap each other. Full hit_rects therefore describe
        hidden card parts too, which makes hover unstable. We approximate the
        visible zone of each card by clipping its rest hit rect at midpoint
        boundaries between neighboring card centers.
        """
        cards = [
            (group, self.get_rest_hit_rect(group))
            for group in self.iter_card_groups()
        ]
        cards.sort(key=lambda item: item[1].centerx)

        visible = []
        for index, (group, rect) in enumerate(cards):
            left = rect.left
            right = rect.right

            if index > 0:
                previous_rect = cards[index - 1][1]
                left = max(left, (previous_rect.centerx + rect.centerx) // 2)
            if index < len(cards) - 1:
                next_rect = cards[index + 1][1]
                right = min(right, (rect.centerx + next_rect.centerx) // 2)

            if right > left:
                visible.append((group, rect.copy().clip((left, rect.top, right - left, rect.height))))

        return visible

    def iter_card_groups(self):
        if hasattr(self.hand_activity, "iter_generated_groups"):
            return tuple(self.hand_activity.iter_generated_groups())
        return ()

    def iter_generated_groups(self):
        """Return visual hand groups for the screen draw pipeline."""
        return self.iter_card_groups()

    def get_base_scale(self, group):
        self.ensure_rest_state(group)
        return self.rest_states[group.id]["scale"]

    def get_base_position(self, group):
        self.ensure_rest_state(group)
        return self.rest_states[group.id]["position"]

    def refresh_rest_states(self):
        for group in self.iter_card_groups():
            if group is self.hovered_group:
                continue
            if group.id in self.selection_actions:
                continue
            self.capture_rest_state(group)

    def capture_rest_state(self, group):
        self.rest_states[group.id] = {
            "position": tuple(group.local_rect.topleft),
            "scale": 1.0 if group.scale_factor is None else group.scale_factor,
        }

    def ensure_rest_state(self, group):
        if group.id not in self.rest_states:
            self.capture_rest_state(group)

    def prune_stale_group_state(self):
        current_groups = {group.id: group for group in self.iter_card_groups()}
        current_ids = set(current_groups)
        self.rest_states = {
            group_id: state
            for group_id, state in self.rest_states.items()
            if group_id in current_ids
        }
        kept_actions = {}
        for group_id, action in self.selection_actions.items():
            is_current = (
                group_id in current_ids
                and getattr(action, "group", current_groups[group_id]) is current_groups[group_id]
            )
            if is_current:
                kept_actions[group_id] = action
            elif hasattr(action, "cancel"):
                action.cancel()
        self.selection_actions = kept_actions
        if self.hovered_group is not None and self.hovered_group.id not in current_ids:
            self.hovered_group = None
        selected_group_id = self.get_selected_group_id()
        if selected_group_id is not None and selected_group_id not in current_ids:
            self.selected_card_context = None
        elif selected_group_id is not None:
            self.selected_card_context = self.get_card_selection_context(
                current_groups[selected_group_id]
            )

    def invalidate_rest_states_if_layout_changed(self):
        current_signature = self.get_hand_layout_signature()
        if current_signature == self._last_hand_layout_signature:
            return
        self._last_hand_layout_signature = current_signature
        self.rest_states = {}
        for action in self.selection_actions.values():
            if hasattr(action, "cancel"):
                action.cancel()
        self.selection_actions = {}
        self.hovered_group = None

    def get_hand_layout_signature(self):
        getter = getattr(self.hand_activity, "get_layout_signature", None)
        if callable(getter):
            return getter()
        return tuple(
            (
                group.id,
                tuple(group.local_rect),
                1.0 if group.scale_factor is None else group.scale_factor,
            )
            for group in self.iter_card_groups()
        )

    def get_selected_group_id(self):
        if not self.selected_card_context:
            return None
        return self.selected_card_context.get("group_id")

    def get_rest_hit_rect(self, group):
        self.get_base_position(group)
        self.get_base_scale(group)
        local_hit_rect = group.local_hit_rect.copy()
        local_hit_rect.topleft = self.get_base_position(group)
        return group.local_rect_to_screen_rect(local_hit_rect)

    def animate_group_to_hover(self, group):
        base_x, base_y = self.get_base_position(group)
        base_scale = self.get_base_scale(group)
        target_scale = base_scale * self.HOVER_SCALE_MULTIPLIER
        target_position = self.calculate_centered_hover_position(
            group,
            (base_x, base_y),
            base_scale,
            target_scale,
        )
        self.selection_actions[group.id] = CardSelectionAction(
            group,
            to_position=target_position,
            to_scale=target_scale,
            duration=self.HOVER_ANIMATION_SECONDS,
        )

    def animate_group_to_rest(self, group):
        if self.is_group_at_rest(group):
            self.selection_actions.pop(group.id, None)
            return
        self.selection_actions[group.id] = CardSelectionAction(
            group,
            to_position=self.get_base_position(group),
            to_scale=self.get_base_scale(group),
            duration=self.HOVER_ANIMATION_SECONDS,
        )

    def calculate_centered_hover_position(self, group, base_position, base_scale, target_scale):
        base_width, base_height = self.calculate_group_scaled_local_size(group, base_scale)
        target_width, target_height = self.calculate_group_scaled_local_size(group, target_scale)
        base_center = (
            base_position[0] + base_width / 2,
            base_position[1] + base_height / 2,
        )
        target_center = (
            base_center[0],
            base_center[1] - self.HOVER_LIFT_PIXELS,
        )
        return (
            int(round(target_center[0] - target_width / 2)),
            int(round(target_center[1] - target_height / 2)),
        )

    @staticmethod
    def calculate_group_scaled_local_size(group, scale):
        return (
            int(round(group.local_rect.width * scale)),
            int(round(group.local_rect.height * scale)),
        )

    def restore_non_hovered_groups(self, hovered_group):
        for group in self.iter_card_groups():
            if group is hovered_group:
                continue
            self.animate_group_to_rest(group)

    def is_group_at_rest(self, group):
        base_position = self.get_base_position(group)
        base_scale = self.get_base_scale(group)
        current_scale = 1.0 if group.scale_factor is None else group.scale_factor
        return (
            tuple(group.local_rect.topleft) == tuple(base_position)
            and abs(current_scale - base_scale) < 0.001
        )

    def update_selection_actions(self, dt):
        running = {}
        for group_id, action in self.selection_actions.items():
            action.update(dt)
            if not action.is_finished():
                running[group_id] = action
        self.selection_actions = running

    def is_finished(self):
        return self._finished

    def finish(self):
        for action in self.selection_actions.values():
            if hasattr(action, "cancel"):
                action.cancel()
        self.selection_actions = {}
        self.hovered_group = None
        self.selected_card_context = None
        self.rest_states = {}
        if self.owns_hand_activity:
            self.hand_activity.finish()
        super().finish()
