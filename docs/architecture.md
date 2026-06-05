# Architecture

`The Fool's Reef` currently uses a data-first GUI architecture on top of
Pygame. Runtime objects are still lightweight Python objects, but the
authoritative description of long-lived GUI groups lives in JSON.

## Current Status

The project has a working runtime composition path:

```text
main.py
    -> RenderEngine
        -> ResourceManager.build_runtime_cache(assets/)
        -> GroupStore.build()
            -> group_config.iter_group_ids()
            -> Group.from_config(group_id, ResourceManager)
        -> TableScreen
            -> Frame tree
            -> active group IDs
```

Game rules are still draft-level. `GameController` stores a fixture
`GameState`, records input events, and returns no real game commands yet.

## Main Idea

`group_config.json` is the source of truth for GUI groups.

It contains:

- group metadata: `role`, `tags`, `rect`, `hit_rect`, `scale_factor`;
- debug display settings: `hide_rect`, `rect_debug_layer_ids`;
- public `manifest_targets`;
- image and text layer definitions.

The runtime path is:

```text
group_config.json
    -> group_config.py API
    -> Group.from_config(group_id, ResourceManager)
        -> runtime Group with pygame surfaces/text layers
            -> GameScreen.draw()
```

`Group` does not own the durable PNG/text decisions. It reads config, builds
runtime layers, and can refresh a changed configured layer through
`GroupStore`.

## Runtime Ownership

```text
main.py
    Composition root. Creates GameController and GroupStore, then starts
    RenderEngine.

RenderEngine
    Owns pygame init, display, event loop, dt clock, and display flip.

ResourceManager
    Low-level asset cache. Reads assets/resource_manifest.json, builds a
    metadata index, and loads pygame Surface frames after display creation.

group_config.json
    Authoritative GUI group/layer metadata.

group_config.py
    Load/save/update API for group_config.json.

Group
    Passive drawable runtime object. Holds rect/hit_rect, scale, role/tags,
    manifest target metadata, and rendered layers.

GroupStore
    Built group registry. Builds groups from group_config.json, returns groups
    by ID, exposes role/tag lookup, and applies manifest target updates.

Frame
    Screen-space container. Owns frame geometry, parent/child frame hierarchy,
    group IDs placed in the frame, hit-testing, and local-to-screen conversion.

GameScreen
    Pygame-facing visual scene. Owns frames, active group IDs, input
    normalization, GUI manifest creation, and visual command dispatch.

TableScreen
    Current concrete screen. Creates the table frame tree and places
    table/left/right/top/bottom player groups.

GameController
    Draft rule boundary. Owns game state and receives normalized input, but
    currently only records clicks/input events.
```

## Current Screen Layout

`screens/table_screen.py` creates one root frame and four player frame pairs:

```text
game_table
    table_group
    left_player_frame
        left_player_portrait -> left_player
    right_player_frame
        right_player_portrait -> right_player
    top_player_frame
        top_player_portrait -> top_player
    bottom_player_frame
        bottom_player_portrait -> bottom_player
```

`TableScreen.put_configured_group()` is defensive: if a configured group is not
present in `GroupStore`, the screen simply skips it.

## GUI Manifest

The public GUI language is built at runtime rather than hand-authored in a
single Python module:

```text
group_config.json manifest_targets
    -> Group.manifest_targets
        -> GroupStore.get_manifest_targets()
            -> GameScreen.get_gui_manifest()
                -> GuiManifest
```

`GuiManifest` exposes public targets such as:

```text
player.left.avatar -> left_player.portrait
player.left.name   -> left_player.player_name_text
table.surface      -> table_group
```

`GameScreen.dispatch_visual_command()` supports these command families:

```text
set_resource target=<manifest target> value=<resource key>
set_text     target=<manifest target> value=<text>
start_activity activity=group.activate|group.deactivate target=<manifest target>
activate_group group_id=<group id>
deactivate_group group_id=<group id>
```

## Assets

`assets/resource_manifest.json` describes raw PNG resources and frame sizes.
`ResourceManager` loads this manifest and can repair missing dimensions.

`assets/gui_manifest.json` is a generated/snapshot artifact of the current GUI
screen, frames, groups, and hierarchy. It should be treated as a diagnostic or
tooling export, not the primary source of truth. The durable source remains
`group_config.json`.

## Compatibility Layer

`groups_store/*_group.py` modules still exist, but they are thin adapters around
`Group.from_config(GROUP_ID, resource_manager)`. `GroupStore` no longer needs
to discover these modules by default; it builds directly from `group_config`.

## Known Architecture Debt

- `group_config.json` contains both `table_group` and `table`; the active
  screen uses `table_group`, while `table` appears to be duplicate legacy data.
- `top_player` and `bottom_player` currently reuse `player.right.*` manifest
  target IDs/tags. Public target IDs must be unique and side-specific before
  controller/settings code relies on them.
- `assets/gui_manifest.json` can drift from runtime state unless regenerated by
  tooling after layout/config changes.
- There is no dependency file in the repository root. Runtime requires at least
  `pygame` and `Pillow`.
- The local `.venv` may be machine-specific and can point to a missing base
  Python installation; verification should use a recreated environment.
