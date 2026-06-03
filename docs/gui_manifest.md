# GUI Manifest

`GUI Manifest` is the public language between controller, settings, and the
visual layer.

It does not describe every internal drawing layer. It names the GUI concepts
that outside code may talk to.

## Targets

Targets map human-readable names to `group_config.json` entries:

```text
player.left.avatar -> group_id left_player, layer portrait
player.left.name   -> group_id left_player, layer player_name_text
table.surface      -> group_id table_group
```

These mappings are declared in `group_config.json` under each group's
`manifest_targets`.

Example:

```python
"manifest_targets": {
    "player.left.avatar": {
        "type": "resource",
        "layer": "portrait",
    },
}
```

## Commands

Controller/settings code can use target names:

```python
VisualCommand(
    type="set_resource",
    target="player.left.avatar",
    value="main_screen.avatars.portrait_4",
)
```

`GameScreen` resolves the target and calls:

```python
group_store.set_group_layer_resource(
    "left_player",
    "portrait",
    "main_screen.avatars.portrait_4",
)
```

## Activities

Activities are also public terms:

```python
VisualCommand(
    type="start_activity",
    activity="group.activate",
    target="table.surface",
)
```

Concrete screens can map these terms to real `Activity` or `Action` classes.

## Relationship To group_config

`group_config.json` is the source of truth.
`group_config.py` is the load/save/update API.

`GuiManifest` is the public address book derived from that config.

```text
group_config.json manifest_targets
    -> group_config.py
    -> Group.manifest_targets
        -> GroupStore.get_manifest_targets()
            -> GuiManifest
```
