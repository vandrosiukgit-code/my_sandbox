"""Visual discard scenario: table cards rise above the table and fade out."""

from actions.bot_card_play_action import BotCardPlayAction, CardFlightGeometry
from activities.base_activity import Activity
from activities.generated_groups import GeneratedGroupRegistry
from animations.base_animation import Animation
from group.group import Group, Layer


class DiscardTableActivity(Activity):
    """Fade cards from play-area slots without changing game state."""

    def __init__(
        self,
        get_table_cards,
        set_table_cards,
        remove_table_card,
        clear_table,
        resource_manager,
        duration=0.5,
        rise_distance=45,
    ):
        super().__init__(duration=0.0)
        self.get_table_cards = get_table_cards
        self.set_table_cards = set_table_cards
        self.remove_table_card = remove_table_card
        self.clear_table = clear_table
        self.resource_manager = resource_manager
        self.discard_duration = max(0.0, float(duration))
        self.rise_distance = int(round(float(rise_distance)))
        self.discard_group_registry = GeneratedGroupRegistry("discard_table.fade_card")
        self.animations = []
        self.initial_delay_seconds = 0.0
        self.delay_elapsed = 0.0
        self.sequence_active = False
        self.discard_started = False

    @property
    def discard_groups(self):
        return self.discard_group_registry.iter_groups()

    @discard_groups.setter
    def discard_groups(self, groups):
        self.discard_group_registry.set_groups(groups)

    def start_discard(self, table_slots, initial_delay_seconds=0.0):
        self.set_table_cards(table_slots)
        self.initial_delay_seconds = max(0.0, float(initial_delay_seconds))
        self.delay_elapsed = 0.0
        self.sequence_active = bool(self.get_table_cards())
        self.discard_started = False
        if not self.sequence_active:
            self.finish()
            return False
        if not self.started:
            self.start()
        if self.initial_delay_seconds <= 0:
            self.start_fade()
        return True

    def update(self, dt):
        if not self.sequence_active:
            return
        if not self.discard_started:
            self.delay_elapsed += dt
            if self.delay_elapsed < self.initial_delay_seconds:
                return
            self.initial_delay_seconds = 0.0
            self.start_fade()
            return

        for animation in tuple(self.animations):
            animation.update(dt)

        if all(animation.is_finished() for animation in self.animations):
            self.finish_sequence()

    def start_fade(self):
        self.discard_started = True
        self.discard_group_registry.clear()
        self.animations = []
        for card in self.get_table_cards():
            group = self.create_discard_group(card)
            animation = DiscardFadeAnimation(
                group,
                source_geometry=card["geometry"],
                duration=self.discard_duration,
                rise_distance=self.rise_distance,
            )
            self.discard_group_registry.append(group)
            self.animations.append(animation)
            self.remove_table_card(card)
            animation.start()

    def create_discard_group(self, card):
        geometry = CardFlightGeometry.from_value(card["geometry"])
        surface = BotCardPlayAction.render_surface(
            geometry.size,
            geometry.angle_degrees,
            self.get_resource_surface(card["resource_key"]),
        )
        rect = surface.get_rect(center=geometry.center)
        return Group(
            self.get_next_discard_group_id(),
            rect=rect,
            layers=[
                Layer(
                    name="card",
                    frames=[surface],
                    layer_type="surface",
                )
            ],
        )

    def get_resource_surface(self, resource_key):
        frames = self.resource_manager.get_frames(resource_key)
        if not frames:
            raise KeyError(f"Discard card resource has no frames: {resource_key!r}")
        return frames[0].copy()

    def finish_sequence(self):
        self.sequence_active = False
        self.clear_table()
        self.discard_group_registry.clear()
        self.animations = []
        self.finish()

    def get_next_discard_group_id(self):
        return self.discard_group_registry.next_id()

    def iter_generated_groups(self):
        return self.discard_group_registry.iter_groups()

    def apply_fixture(self, fixture):
        """Accept the screen fixture protocol; runner starts discard explicitly."""
        _ = fixture


class DiscardFadeAnimation(Animation):
    """Move one card upward in screen space and fade its alpha to zero."""

    animated_properties = ("screen_rect", "alpha")
    coordinate_space = "screen"

    def __init__(self, group, source_geometry, duration=0.5, rise_distance=45):
        super().__init__(duration=duration, max_frame_dt=1 / 120)
        self.group = group
        self.source_geometry = CardFlightGeometry.from_value(source_geometry)
        self.rise_distance = int(round(float(rise_distance)))
        self.base_surface = group.get_primary_layer_frames()[0].copy()

    def start(self):
        super().start()
        self.apply(0.0)

    def apply(self, progress):
        progress = max(0.0, min(1.0, float(progress)))
        center_x, center_y = self.source_geometry.center
        center_y = int(round(center_y - self.rise_distance * progress))
        rect = self.base_surface.get_rect(center=(center_x, center_y))

        surface = self.base_surface.copy()
        surface.set_alpha(max(0, min(255, int(round(255 * (1.0 - progress))))))

        self.group.set_rect(rect)
        self.group.set_primary_layer_frames([surface], position=(0, 0))
