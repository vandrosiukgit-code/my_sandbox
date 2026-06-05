# GUI Manifest

`GuiManifest` is the public language between controller/settings code and the
visual layer. It intentionally exposes stable GUI concepts instead of every
internal drawing layer.

## Source Of Truth

Public targets are declared in `group_config.json` under each group's
`manifest_targets` block.

```json
{
  "manifest_targets": {
    "player.left.avatar": {
      "type": "resource",
      "layer": "portrait",
      "description": "Left player portrait image."
    },
    "player.left.name": {
      "type": "text",
      "layer": "player_name_text",
      "description": "Left player display name."
    }
  }
}
```

At runtime:

```text
group_config.json
    -> Group.from_config()
    -> Group.manifest_targets
    -> GroupStore.get_manifest_targets()
    -> GameScreen.get_gui_manifest()
```

## Target Types

Current target types:

```text
resource  updates one configured image layer resource_key
text      updates one configured text layer text value
group     names a group-level visual object
```

`GroupStore.apply_target_value()` currently supports value updates for
`resource` and `text` targets.

## Commands

Controller/settings code should use target names, not group/layer internals:

```python
VisualCommand(
    type="set_resource",
    target="player.left.avatar",
    value="main_screen.avatars.portrait_4",
)
```

`GameScreen` resolves the target and delegates to `GroupStore`:

```text
player.left.avatar
    -> group_id left_player
    -> layer portrait
    -> set_group_layer_resource(...)
```

Text updates follow the same path:

```python
VisualCommand(
    type="set_text",
    target="player.left.name",
    value="Captain",
)
```

## Activities

`core.gui_manifest.DEFAULT_GUI_ACTIVITIES` currently defines:

```text
group.activate
group.deactivate
```

These are public activity terms. The base `GameScreen` maps them to active
group ID changes. Later screens can map richer terms to concrete `Activity` or
`Action` classes.

```python
VisualCommand(
    type="start_activity",
    activity="group.activate",
    target="table.surface",
)
```

## Current Caution

Manifest target IDs must be unique. `group_config.json` currently has duplicated
`player.right.*` targets on right/top/bottom player groups. This should be
normalized to side-specific IDs before target-based settings are treated as
stable API.
