# Current Architecture Snapshot

Date: 2026-06-30

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
- `Group` stores parent-frame-local geometry and exposes derived screen-space
  rects for drawing and hit-testing.
- `GroupStore.build()` builds configured groups directly from `group_config`.
- `TableScreen` creates the current table layout with left/right/top/bottom
  player panels.
- `Frame` stores parent-local geometry and converts nested frame/group
  coordinates to screen coordinates.
- `GameScreen` normalizes mouse input into `ScreenInputEvent`.
- `GameScreen` dispatches `VisualCommand` objects through public GUI targets.
- `GuiManifest` is derived from configured group `manifest_targets`.
- `core/durak` now contains autonomous Durak session logic that can conduct
  bot-vs-bot games without GUI participation.

## Coordinate Contract

- Each GUI hierarchy level owns a `pygame.Rect`.
- `rect.topleft` is stored relative to the parent rect.
- `rect.size` belongs to the object itself.
- `Frame.scale_factor` is inherited by descendants until a child frame, group,
  or activity defines its own scale.
- A child `scale_factor` replaces the inherited parent scale; scales are not
  multiplied together.
- Screen-space rects are derived runtime projections used for draw, hit-test,
  and movement interpolation.
- Movement animations may run in absolute screen coordinates, but their final
  position should be resolved back into the object's local rect.
- Fractional scale and interpolation are allowed only during calculation. Values
  that enter `pygame.Rect`, fixture positions, layer positions, blit positions,
  or scaled surface sizes are rounded to integer pixels.

## Contract Layers

- Domain contract:
  `core/durak` domain actions, domain events, snapshots, and autonomous
  session flow.
- Adapter contract:
  `core/game_controller.py` translation between domain results and GUI-facing
  controller responses.
- GUI contract:
  `game_screen/events.py` transport types for screen/activity orchestration.

## Bottom Hand Layout Contract

- The bottom player's hand fan is a dedicated interactive layout, not a bot-hand
  variant.
- `TableScreen.calculate_bottom_player_hand_available_screen_rect()` is the
  authoritative source of the bottom fan corridor.
- That corridor may depend only on stable frame geometry:
  - `bottom_player_hand` frame;
  - `bottom_player_portrait` frame;
  - the legacy anchor slot frames `cards_slot_frame` through
    `cards_slot_frame_7`.
- Extra table slots such as `cards_slot_frame_8+`, dynamic card occupancy,
  generated groups, and transient animation positions must not change bottom
  fan geometry.
- `PlayerHandActivity.set_fan_area_local_rect()` consumes that corridor as an
  external layout contract and must not infer replacement geometry from bot
  hands or rendered card bounds.

## Table Slot Visual Contract

- Table card slots are owned visually by `CardsSlotActivityDecorator`.
- Slot card order is logical and stable:
  - index `0` is the first card in the slot;
  - index `1` is the second card in the slot.
- Visual stacking must follow the same order:
  - the first card is drawn first and stays visually below;
  - the second card is drawn after it and stays visually above.
- This rule applies equally to:
  - direct slot rendering;
  - placement through `PlayAreaSlotsActivity`;
  - player-turn commit through `PlayerTurnActivity`;
  - bot-turn commit through `BotTurnActivity`.
- Nested activity aggregation must preserve slot draw order through
  `iter_groups_in_draw_order()` instead of reconstructing order from
  `iter_generated_groups()`.
- During the final phase of a player turn, the transient flight group must be
  drawn above settled slot cards until the commit completes.

## What Is Still Draft

- `core/game_controller.py` still contains first-playable adapter logic that
  should be reduced to a pure translator over `core/durak`.
- `Activity` and `Action` remain base contracts, but the table screen already
  uses concrete visual pipelines for:
  - player hand rendering;
  - bot hand rendering;
  - player turn animation;
  - bot turn animation;
  - play-area slot aggregation and overflow transfer.

## Current Architecture Risks

- `assets/gui_manifest.json` is a generated snapshot/export and can drift from
  the live `TableScreen`.
- The local `.venv` can be machine-specific and should be recreated before
  verification.
- Draw-order regressions can reappear if a parent activity consumes only
  `iter_generated_groups()` and ignores a child `iter_groups_in_draw_order()`
  contract.

## Recommended Next Steps

1. Recreate the virtual environment from `requirements.txt`.
2. Add a small manifest validation script for duplicate target IDs, missing
   resources, and stale group/frame references.
3. Reduce `core/game_controller.py` to a pure adapter over the domain contract.
4. Connect GUI visual flows to domain events instead of duplicating rules.
