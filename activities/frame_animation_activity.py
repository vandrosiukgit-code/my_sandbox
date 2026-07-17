"""Long-lived visual state backed by finite reversible frame Actions."""

from activities.base_activity import Activity


class FrameAnimationActivity(Activity):
    """Own transitions and transforms for one injected frame-animation Group."""

    def __init__(
        self,
        overlay_group,
        *,
        action_class,
        layer_names,
        expected_frame_count,
        frame_duration,
        overlay_local_position=None,
        rotation_degrees=0.0,
        flip_x=False,
        flip_y=False,
    ):
        super().__init__(group_ids=(overlay_group.id,), duration=0.0)
        self.overlay_group = overlay_group
        self.action_class = action_class
        self.layer_names = tuple(layer_names)
        self.frame_duration = max(0.001, float(frame_duration))
        self.rotation_degrees = float(rotation_degrees) % 360.0
        self.flip_x = bool(flip_x)
        self.flip_y = bool(flip_y)
        self._action_transform_pending = bool(
            self.rotation_degrees or self.flip_x or self.flip_y
        )
        if overlay_local_position is not None:
            self.overlay_group.set_local_position(*overlay_local_position)
        frame_counts = {
            len(overlay_group.get_layer_frames(layer_name))
            for layer_name in self.layer_names
        }
        if frame_counts != {int(expected_frame_count)}:
            raise ValueError(
                f"Frame animation overlay must contain exactly {int(expected_frame_count)} frames"
            )
        self.frame_count = frame_counts.pop()
        self.prepare_overlay_frames()
        self.current_frame_index = 0
        self.target_frame_index = 0
        self.state = "idle"
        self.transition_active = False
        self.transition_id = 0
        self.completed_transition_id = 0
        self.current_action = None

    @property
    def frame_elapsed(self):
        if self.current_action is None:
            return 0.0
        return self.current_action.frame_elapsed

    def prepare_overlay_frames(self):
        """Allow specializations to normalize non-transform frame state."""

    def start(self):
        if self.started:
            return
        super().start()
        self.apply_frame(0)

    def update(self, dt):
        if not self.started:
            self.start()
        if self.current_action is None:
            return
        self.current_action.update(dt)
        self.current_frame_index = self.current_action.current_frame_index
        if self.current_action.is_finished():
            self.current_action = None
            self.complete_transition()

    def start_transition(self):
        """Play toward the persistent active state."""
        return self.begin_transition(self.frame_count - 1, "entering", "active")

    def finish_transition(self):
        """Return to idle by playing the same frames in reverse."""
        return self.begin_transition(0, "exiting", "idle")

    def begin_transition(self, target_frame_index, transition_state, completed_state):
        if not self.started:
            self.start()
        target_frame_index = int(target_frame_index)
        if target_frame_index == self.target_frame_index and (
            self.transition_active or self.current_frame_index == target_frame_index
        ):
            return self.transition_id
        if self.current_action is not None:
            self.current_frame_index = self.current_action.current_frame_index
            self.current_action.cancel()
        self.transition_id += 1
        self.target_frame_index = target_frame_index
        self.state = transition_state
        self._completed_state = completed_state
        action_options = self.build_action_options()
        self.current_action = self.action_class(
            self.overlay_group,
            layer_names=self.layer_names,
            start_frame_index=self.current_frame_index,
            target_frame_index=self.target_frame_index,
            frame_duration=self.frame_duration,
            **action_options,
        )
        self._action_transform_pending = False
        self.current_action.start()
        self.transition_active = not self.current_action.is_finished()
        if not self.transition_active:
            self.current_action = None
            self.complete_transition()
        return self.transition_id

    def build_action_options(self):
        return {}

    def complete_transition(self):
        self.transition_active = False
        self.state = self._completed_state
        self.completed_transition_id = self.transition_id

    def is_transition_complete(self, transition_id):
        return self.completed_transition_id >= int(transition_id)

    def apply_frame(self, frame_index):
        self.current_frame_index = max(0, min(int(frame_index), self.frame_count - 1))
        for layer_name in self.layer_names:
            self.overlay_group.set_layer_frame(layer_name, self.current_frame_index)

    def apply_fixture(self, fixture):
        if isinstance(fixture, dict) and "frame_duration" in fixture:
            self.frame_duration = max(0.001, float(fixture["frame_duration"]))
            if self.current_action is not None:
                self.current_action.frame_duration = self.frame_duration

    def is_finished(self):
        return False

    def finish(self):
        if self.current_action is not None:
            self.current_action.cancel()
            self.current_action = None
        self.apply_frame(0)
        self.state = "idle"
        self.transition_active = False
        super().finish()
