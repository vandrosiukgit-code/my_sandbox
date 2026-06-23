# Screen Layout Refactor Backlog

## Purpose

Fix hidden coupling between screen layout and dynamic visual content.

The issue was exposed by the `bot_turn` dev test: moving cards into play-area
slots changes slot contents, and `TableScreen` recalculates the bottom player
hand area from those changing visual bounds.

Target rule:

```text
Screen layout may depend on stable Frame geometry.
Screen layout must not depend on Activity-generated Group geometry or Action
transient Group positions.
```

## Problem Statement

Current behavior:

```text
BotTurnActivity
    -> BotCardPlayAction
        -> target slot set_cards()
            -> slot generated groups change
                -> TableScreen layout calculations observe changed slot bounds
                    -> bottom player hand fan area changes
```

Expected behavior:

```text
BotTurnActivity
    -> BotCardPlayAction
        -> target slot set_cards()
            -> slot contents change
                -> unrelated screen layout remains stable
```

## Scope

In scope:

- `GameScreen`/screen-level layout contract;
- `TableScreen` slot/bottom-hand layout calculations;
- helper APIs for frame-based layout reads;
- architecture/code-review documentation;
- dev-test validation with `bot_turn`.

Out of scope:

- game rules;
- controller state model;
- card legality;
- broad screen rewrite;
- replacing `BotTurnActivity` or `BotCardPlayAction`.

## P0. Document the Screen Layout Contract [done]

Files:

- `docs/rules/architecture_checklist.md`
- `docs/rules/code_review.md`
- `docs/rules/refactor_rules.md`
- optional: `docs/architecture.md`

Tasks:

- Add a rule that screen layout must use stable `Frame` geometry.
- Mark generated group bounds and action-transient group positions as invalid
  inputs for unrelated screen layout.
- Define the only acceptable exception: an explicit layout-requirement API,
  not arbitrary reads from Activity internals.

Acceptance criteria:

- Review checklist contains a clear red flag for layout depending on
  `activity.iter_generated_groups()`, `activity.calculate_fan_rect()`,
  generated `group.rect`, or animated group positions.
- Refactor rules name the safe replacement: use frame rect/content rect or a
  named layout requirement API.

## P1. Add Frame-Based Screen Layout Helpers [done]

Files:

- `game_screen/game_screen.py`
- possibly `game_screen/frame.py`

Tasks:

- Add small public helpers for stable frame geometry reads, for example:

```python
get_frame_screen_rect(frame_id)
get_frame_content_screen_rect(frame_id)
get_frame_screen_rects(frame_ids)
```

- Return copies so callers cannot mutate frame state accidentally.
- Keep names explicit about coordinate space.

Acceptance criteria:

- Screen code can read stable frame geometry without reaching into activity
  generated groups.
- Helpers do not change frame ownership or layout behavior.
- Coordinate names are explicit.

## P2. Refactor TableScreen Bottom-Hand Layout [done]

Files:

- `screens/table_screen.py`

Tasks:

- Split stable frame geometry from dynamic slot content geometry.
- Introduce explicit methods:

```python
get_play_area_slot_frame_screen_rects()
get_play_area_slot_content_screen_rects()  # only if still needed for debug
```

- Make bottom hand layout use only `get_play_area_slot_frame_screen_rects()`.
- Ensure these methods do not call slot activity content methods or inspect
  generated groups.
- Keep existing visual placement behavior unless it directly depends on dynamic
  content.

Acceptance criteria:

- `configure_bottom_player_hand_fan_area()` is stable while cards are animated
  into slots.
- `calculate_bottom_player_hand_available_screen_rect()` does not depend on
  slot generated groups or action-transient positions.
- `bot_turn` dev test no longer changes bottom player hand geometry as cards
  enter slots.

## P3. Prevent Per-Frame Redundant Relayout [done]

Files:

- `screens/table_screen.py`
- possibly `activities/player_hand_activity.py`

Tasks:

- Add a layout signature around bottom-hand fan area inputs.
- Only call `set_fan_area_local_rect()` when the stable frame-based signature
  changes.

Candidate signature:

```text
bottom_player_hand frame rect
play-area slot frame rects
screen size / relevant scale
```

Acceptance criteria:

- Bottom-hand relayout is idempotent.
- Changing slot card contents does not change the signature.
- Actual frame layout changes still update the bottom hand area.

## P4. Validate with Dev Test [manual]

Files:

- `docs/dev_tests.md`
- `fixtures/action_runner.py`

Tasks:

- Run:

```powershell
& ".\.venv\Scripts\python.exe" fixtures\action_runner.py run player_card_play
```

- Observe the `player_card_play` action run.
- Record whether bottom player hand geometry remains stable.
- Record any remaining failures separately as Activity, Action, slot commit,
  hand cleanup, layout, or rendering.

Acceptance criteria:

- GUI launches.
- Bot cards move into slots.
- Bottom player hand does not resize/reposition because slot contents changed.
- Failures are reported with concrete evidence.

## P5. Optional Automated Guard [deferred]

Files:

- tests, if/when test structure exists

Tasks:

- Add a non-rendering or headless smoke check that captures the bottom-hand fan
  area before and after slot content changes.
- Assert the stable layout rect is unchanged when only slot card contents
  change.

Acceptance criteria:

- Regression check fails if screen layout starts reading dynamic slot content
  again.

## Implementation Order

Recommended order:

1. P0: documentation contract.
2. P1: frame-based helper API.
3. P2: local `TableScreen` fix.
4. P3: relayout signature, if needed after P2.
5. P4: manual dev-test validation.
6. P5: automated guard later.

## Risk Notes

- Do not move layout decisions into `Activity`.
- Do not make `Frame` aware of game meaning.
- Do not hide the issue by disabling bottom-hand layout only in
  `fixtures/action_runner.py`.
- Do not use generated group bounds for screen layout unless an explicit
  layout-requirement contract is introduced.
