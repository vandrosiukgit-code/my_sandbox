"""High-level activity for selecting a card from a player hand."""

from activities.base_activity import Activity
from actions import CardSelectionAction


class CardSelectionActivity(Activity):
    """Own the visual process of choosing a card from a hand.

    It watches generated hand-card groups, enlarges the card under the cursor,
    and exposes controller-facing card context for selection input.
    """

    HOVER_SCALE_MULTIPLIER = 1.18
    HOVER_ANIMATION_SECONDS = 0.08
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
        if getattr(input_event, "type", None) != "double_click":
            return {}
        if getattr(input_event, "button", None) != "left":
            return {}
        clicked_group = self.find_selectable_card_at(getattr(input_event, "screen_pos", None))
        if clicked_group is None:
            return {}
        return {"selected_card": self.select_card_context(clicked_group)}

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
        owner = self.get_generated_group_owner()
        if owner is None:
            return ()
        if hasattr(owner, "iter_generated_groups"):
            return tuple(owner.iter_generated_groups())
        return tuple(getattr(owner, "generated_groups", ()))

    def iter_generated_groups(self):
        """Return visual hand groups for the screen draw pipeline."""
        return self.iter_card_groups()

    def get_generated_group_owner(self):
        if hasattr(self.hand_activity, "generated_groups"):
            return self.hand_activity
        if hasattr(self.hand_activity, "hand_activity"):
            return self.hand_activity.hand_activity
        return None

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
        target_position = (base_x, base_y - self.HOVER_LIFT_PIXELS)
        target_scale = self.get_base_scale(group) * self.HOVER_SCALE_MULTIPLIER
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
