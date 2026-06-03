"""Public GUI language used by controller, settings, and visual activities."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GuiTarget:
    """Public address for one configurable or interactive GUI object."""

    id: str
    type: str
    group_id: str | None = None
    layer: str | None = None
    frame_id: str | None = None
    config_key: str | None = None
    description: str | None = None

    def to_payload(self):
        payload = {
            "id": self.id,
            "type": self.type,
            "group_id": self.group_id,
            "layer": self.layer,
            "frame_id": self.frame_id,
            "config_key": self.config_key,
        }
        if self.description is not None:
            payload["description"] = self.description
        return payload


@dataclass(frozen=True)
class GuiActivity:
    """Public activity term that can be requested by a controller command."""

    id: str
    type: str = "activity"
    required: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()
    description: str | None = None

    def to_payload(self):
        payload = {
            "id": self.id,
            "type": self.type,
            "required": list(self.required),
            "optional": list(self.optional),
        }
        if self.description is not None:
            payload["description"] = self.description
        return payload


@dataclass
class GuiManifest:
    """Public GUI manifest without internal Group layer details."""

    targets: dict[str, GuiTarget] = field(default_factory=dict)
    frames: dict[str, dict] = field(default_factory=dict)
    activities: dict[str, GuiActivity] = field(default_factory=dict)

    def get_target(self, target_id):
        try:
            return self.targets[target_id]
        except KeyError as error:
            raise KeyError(f"Unknown GUI target: {target_id}") from error

    def get_activity(self, activity_id):
        try:
            return self.activities[activity_id]
        except KeyError as error:
            raise KeyError(f"Unknown GUI activity: {activity_id}") from error

    def to_payload(self):
        return {
            "targets": {
                target_id: target.to_payload()
                for target_id, target in sorted(self.targets.items())
            },
            "frames": dict(sorted(self.frames.items())),
            "activities": {
                activity_id: activity.to_payload()
                for activity_id, activity in sorted(self.activities.items())
            },
        }


DEFAULT_GUI_ACTIVITIES = {
    "group.activate": GuiActivity(
        id="group.activate",
        required=("target",),
        description="Make a manifest target group active on the current screen.",
    ),
    "group.deactivate": GuiActivity(
        id="group.deactivate",
        required=("target",),
        description="Remove a manifest target group from the current screen.",
    ),
}
