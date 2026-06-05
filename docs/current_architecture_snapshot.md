# Current Architecture Snapshot

Date: 2026-06-05

This document records the current observed architecture. It is intentionally
shorter and more factual than the historical refactor backlog.

## Runtime Shape

```text
main.py
    -> RenderEngine
        -> pygame display
        -> ResourceManager.build_runtime_cache(assets/)
        -> GroupStore.build()
            -> group_config.iter_group_ids()
            -> Group.from_config(group_id, ResourceManager)
        -> TableScreen
            -> Frame tree
            -> active group IDs
        -> GameScreen event/update/draw loop
```

## What Is Implemented

- `main.py` is the composition root and starts the pygame runtime.
- `ResourceManager` owns low-level PNG/resource loading.
- `group_config.json` owns durable GUI group metadata and layer definitions.
- `group_config.py` exposes load/save/update helpers for that JSON.
- `Group.from_config()` builds runtime image/text layers.
- `GroupStore.build()` builds configured groups directly from `group_config`.
- `TableScreen` creates the current table layout with left/right/top/bottom
  player panels.
- `GameScreen` normalizes mouse input into `ScreenInputEvent`.
- `GameScreen` dispatches `VisualCommand` objects through public GUI targets.
- `GuiManifest` is derived from configured group `manifest_targets`.

## What Is Still Draft

- `GameController` has no real game rules yet. It stores a fixture
  `GameState`, records clicks/input events, and returns no real commands.
- `Activity` and `Action` are still base contracts; no concrete visual process
  pipeline is wired into gameplay.
- Cards exist as assets and fixture state, but card groups are not yet part of
  the current `TableScreen` layout.

## Current Architecture Risks

- `group_config.json` contains duplicate/legacy table entries: active
  `table_group` and apparently stale `table`.
- `top_player` and `bottom_player` reuse `player.right.*` manifest target IDs.
  Public target IDs should be unique before settings/controller code relies on
  them.
- Some tags/descriptions in `group_config.json` still say `right_player` for
  non-right players.
- `assets/gui_manifest.json` is a snapshot/export and can drift from the live
  `TableScreen` unless regenerated.
- No dependency file is present in the project root. Runtime needs at least
  `pygame` and `Pillow`.
- The local `.venv` can be machine-specific and should be recreated before
  verification.

## Recommended Next Steps

1. Normalize `group_config.json` public targets:
   `player.top.*`, `player.bottom.*`, `player.right.*`, `player.left.*`.
2. Remove or migrate duplicate `table` config after confirming no tool uses it.
3. Add a dependency file and a documented environment setup path.
4. Add a small manifest validation script for duplicate target IDs, missing
   resources, and stale group/frame references.
5. Decide whether `assets/gui_manifest.json` is generated output and document
   the generator command.
