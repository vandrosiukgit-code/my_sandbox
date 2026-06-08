"""High-level activity for selecting a card from a player hand."""

from activities.base_activity import Activity
from animations import CardSelectionAnimation


class CardSelectionActivity(Activity):
    """Own the visual process of choosing a card from a hand.

    It watches generated hand-card groups, enlarges the card under the cursor,
    and starts the player-turn activity on double left click.
    """

    HOVER_SCALE_MULTIPLIER = 1.18
    HOVER_ANIMATION_SECONDS = 0.08
    HOVER_LIFT_PIXELS = 28
    HOVER_HYSTERESIS_PIXELS = 8
    HOVER_EDGE_CARD_HYSTERESIS_PIXELS = 18

    def __init__(self, hand_activity, player_turn_activity=None):
        super().__init__(duration=0.0)
        self.hand_activity = hand_activity
        self.player_turn_activity = player_turn_activity
        self.hovered_group = None
        self.selection_animations = {}

    def start(self):
        super().start()
        self.hand_activity.start()

    def update(self, dt):
        if not self.started:
            self.start()
        self.hand_activity.update(dt)
        self.refresh_rest_states()
        self.update_selection_animations(dt)

    def draw(self, screen):
        if hasattr(self.hand_activity, "draw"):
            self.hand_activity.draw(screen)

    def apply_fixture(self, fixture):
        if hasattr(self.hand_activity, "apply_fixture"):
            self.hand_activity.apply_fixture(fixture)

    def handle_input(self, input_event):
        if input_event.type == "hover":
            self.handle_hover(input_event.screen_pos)
            return False
        if input_event.type == "double_click" and input_event.button == "left":
            selected_group = self.find_card_at(input_event.screen_pos)
            if selected_group is not None:
                self.start_player_turn(selected_group)
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

    def start_player_turn(self, selected_group):
        self.selected_group = selected_group
        if self.player_turn_activity is not None:
            self.player_turn_activity.start()

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
        return tuple(getattr(owner, "generated_groups", ()))

    def get_generated_group_owner(self):
        if hasattr(self.hand_activity, "generated_groups"):
            return self.hand_activity
        if hasattr(self.hand_activity, "hand_activity"):
            return self.hand_activity.hand_activity
        return None

    def get_base_scale(self, group):
        self.ensure_rest_state(group)
        return group._card_selection_base_scale

    def get_base_position(self, group):
        self.ensure_rest_state(group)
        return group._card_selection_base_position

    def refresh_rest_states(self):
        for group in self.iter_card_groups():
            if group is self.hovered_group:
                continue
            if group.id in self.selection_animations:
                continue
            self.capture_rest_state(group)

    @staticmethod
    def capture_rest_state(group):
        group._card_selection_base_position = tuple(group.local_rect.topleft)
        group._card_selection_base_scale = 1.0 if group.scale_factor is None else group.scale_factor

    @staticmethod
    def ensure_rest_state(group):
        if not hasattr(group, "_card_selection_base_position"):
            group._card_selection_base_position = tuple(group.local_rect.topleft)
        if not hasattr(group, "_card_selection_base_scale"):
            group._card_selection_base_scale = 1.0 if group.scale_factor is None else group.scale_factor

    def get_rest_hit_rect(self, group):
        self.get_base_position(group)
        self.get_base_scale(group)
        local_hit_rect = group.local_hit_rect.copy()
        local_hit_rect.topleft = group._card_selection_base_position
        return group.local_rect_to_screen_rect(local_hit_rect)

    def animate_group_to_hover(self, group):
        base_x, base_y = self.get_base_position(group)
        target_position = (base_x, base_y - self.HOVER_LIFT_PIXELS)
        target_scale = self.get_base_scale(group) * self.HOVER_SCALE_MULTIPLIER
        self.selection_animations[group.id] = CardSelectionAnimation(
            group,
            to_position=target_position,
            to_scale=target_scale,
            duration=self.HOVER_ANIMATION_SECONDS,
        )

    def animate_group_to_rest(self, group):
        if self.is_group_at_rest(group):
            self.selection_animations.pop(group.id, None)
            return
        self.selection_animations[group.id] = CardSelectionAnimation(
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

    def update_selection_animations(self, dt):
        running = {}
        for group_id, animation in self.selection_animations.items():
            animation.update(dt)
            if not animation.is_finished():
                running[group_id] = animation
        self.selection_animations = running

    def is_finished(self):
        return self._finished

    def finish(self):
        self.hand_activity.finish()
        super().finish()
