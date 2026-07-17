"""Finite reversible transition across one or more synchronized frame layers."""

from actions.base_action import Action


class FrameAnimationAction(Action):
    """Play a synchronized frame range without owning persistent visual state."""

    def __init__(
        self,
        overlay_group,
        *,
        layer_names,
        start_frame_index=0,
        target_frame_index,
        frame_duration=0.045,
        expected_frame_count=None,
        hold_frame_count=0,
        return_frame_index=None,
    ):
        self.overlay_group = overlay_group
        self.layer_names = tuple(layer_names)
        if not self.layer_names:
            raise ValueError("Frame animation requires at least one layer")
        frame_counts = {
            len(overlay_group.get_layer_frames(layer_name))
            for layer_name in self.layer_names
        }
        if len(frame_counts) != 1 or next(iter(frame_counts), 0) < 2:
            raise ValueError("Frame animation layers must share at least two frames")
        self.frame_count = frame_counts.pop()
        if expected_frame_count is not None and self.frame_count != int(expected_frame_count):
            raise ValueError(
                f"Frame animation requires exactly {int(expected_frame_count)} frames"
            )
        self.current_frame_index = self.clamp_frame_index(start_frame_index)
        self.target_frame_index = self.clamp_frame_index(target_frame_index)
        self.frame_duration = max(0.001, float(frame_duration))
        self.hold_frame_count = max(0, int(hold_frame_count))
        self.return_frame_index = (
            None
            if return_frame_index is None
            else self.clamp_frame_index(return_frame_index)
        )
        self.frame_elapsed = 0.0
        self.phase = "forward"
        super().__init__(group_ids=(overlay_group.id,))

    def start(self):
        super().start()
        self.frame_elapsed = 0.0
        self.phase = "forward"
        if not self.is_group_at_frame(self.current_frame_index):
            self.apply_frame(self.current_frame_index)
        if self.current_frame_index == self.target_frame_index:
            self.complete_current_leg()

    def update(self, dt):
        if self._finished:
            return
        if not self.started:
            self.start()
        if self._finished:
            return

        self.frame_elapsed += max(0.0, float(dt or 0.0))
        while not self._finished:
            if self.phase == "holding":
                hold_duration = self.hold_frame_count * self.frame_duration
                if self.frame_elapsed + 1e-12 < hold_duration:
                    break
                self.frame_elapsed -= hold_duration
                self.begin_return_leg()
                continue
            if self.frame_elapsed + 1e-12 < self.frame_duration:
                break
            self.frame_elapsed -= self.frame_duration
            direction = 1 if self.target_frame_index > self.current_frame_index else -1
            self.apply_frame(self.current_frame_index + direction)
            if self.current_frame_index == self.target_frame_index:
                self.complete_current_leg()

    def complete_current_leg(self):
        if self.phase == "forward" and self.return_frame_index is not None:
            if self.hold_frame_count:
                self.phase = "holding"
            else:
                self.begin_return_leg()
            return
        self.finish()

    def begin_return_leg(self):
        self.phase = "returning"
        self.target_frame_index = self.return_frame_index
        if self.current_frame_index == self.target_frame_index:
            self.finish()

    def cancel(self):
        """Stop at the current frame so the owner can reverse without a jump."""
        super().cancel()

    def apply_frame(self, frame_index):
        self.current_frame_index = self.clamp_frame_index(frame_index)
        for layer_name in self.layer_names:
            self.overlay_group.set_layer_frame(layer_name, self.current_frame_index)

    def clamp_frame_index(self, frame_index):
        return max(0, min(int(frame_index), self.frame_count - 1))

    def is_group_at_frame(self, frame_index):
        return all(
            self.overlay_group.get_layer(layer_name).current_frame_index == frame_index
            for layer_name in self.layer_names
        )
