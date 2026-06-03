# Architecture

`The Fool's Reef` uses a data-first GUI model.

## Main Idea

`group_config.json` is the source of truth for GUI groups.

It contains group metadata, public manifest targets, and graphical/text layers.
External modules may read and edit it through `group_config.py`. `Group` no
longer owns PNG-resource decisions; it reads the current config and draws the
resulting runtime layers.

```text
group_config.json
    -> group_config.py API
    -> Group.from_config(group_id, ResourceManager)
        -> runtime Group
            -> GameScreen.draw()
```

## Runtime Flow

```text
main.py
    -> ResourceManager.build_runtime_cache()
    -> GroupStore.build()
        -> group_config.iter_group_ids()
        -> Group.from_config(group_id, ResourceManager)
    -> TableScreen
    -> RenderEngine
```

## group_config.json

The config contains one entry per group:

```json
{
  "groups": {
    "left_player": {
        "role": "player_panel",
        "rect": [0, 0, 200, 200],
        "manifest_targets": {
            "player.left.avatar": {
                "type": "resource",
                "layer": "portrait",
            }
        },
        "layers": [
            {
                "name": "portrait",
                "type": "image",
                "resource_key": "main_screen.avatars.portrait_2"
            }
        ]
    }
  }
}
```

If a settings module wants another portrait, it changes:

```python
group_config.set_layer_resource(
    "left_player",
    "portrait",
    "main_screen.avatars.portrait_4",
)
```

Then the running group can refresh that layer through `GroupStore`.

## Group

`Group` is a runtime drawing script:

```text
read group_config
load frames through ResourceManager
render layers
refresh changed layers when config changes
```

It stores runtime surfaces and geometry, not the authoritative PNG metadata.

Important methods:

```text
Group.from_config(group_id, resource_manager)
group.reload_layers_from_config(resource_manager)
group.set_layer_resource_from_config(layer_name, resource_key, resource_manager)
group.set_layer_text_from_config(layer_name, text)
```

## GroupStore

`GroupStore` stores built `Group` objects and gives external modules a safe API
for refreshing config-driven groups:

```text
set_group_layer_resource(group_id, layer_name, resource_key)
set_group_layer_text(group_id, layer_name, text)
get_manifest_targets()
apply_target_value(target, value)
```

## groups_store/

`GroupStore` no longer needs a builder module for each configured group. It
builds groups directly from `group_config.json`.

Existing `groups_store/*` modules are thin compatibility adapters only.

## GUI Manifest

The manifest is the public language for controller/settings commands. It does
not expose all internal layers. It maps readable targets to group-config layers:

```text
player.left.avatar -> group left_player, layer portrait
player.left.name   -> group left_player, layer player_name_text
```

Example command:

```python
VisualCommand(
    type="set_resource",
    target="player.left.avatar",
    value="main_screen.avatars.portrait_4",
)
```

`GameScreen` resolves the target through `GuiManifest` and delegates the change
to `GroupStore`.

## Ownership

```text
group_config.json -> source of truth for GUI group metadata and layers
group_config.py   -> load/save/update API for group_config.json
Group             -> runtime drawing script built from group_config
GroupStore       -> built groups and refresh/apply API
groups_store/*   -> thin group_id builders
GuiManifest      -> public target/activity language
GameController   -> rules and public VisualCommand terms
GameScreen       -> pygame adapter and command dispatch
ResourceManager  -> low-level PNG frame cache
```
