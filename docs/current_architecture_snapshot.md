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

- `assets/gui_manifest.json` is a generated snapshot/export and can drift from
  the live `TableScreen` unless regenerated with
  `python scripts/update_gui_manifest.py`.
- The local `.venv` can be machine-specific and should be recreated before
  verification.

## Recommended Next Steps

1. Recreate the virtual environment from `requirements.txt`.
2. Add a small manifest validation script for duplicate target IDs, missing
   resources, and stale group/frame references.
3. Start implementing real `GameController` rules and card group placement.
