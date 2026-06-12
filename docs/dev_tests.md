# Dev Tests

## Purpose

Dev tests are lightweight, developer-operated validation scenarios for visual
GUI behavior that is not yet covered by automated tests.

They are used to validate runtime behavior in the real Pygame engine:

- Activity lifecycle;
- Action sequencing;
- frame/group placement;
- visual state commit after animation;
- fixture-driven GUI scenarios.

Dev tests are not a replacement for unit tests or integration tests. They are
manual smoke tests for high-risk visual flows while the gameplay layer is still
under construction.

## Test Type

In QA terminology, these scenarios are closest to:

- manual smoke tests;
- exploratory visual tests;
- scenario-based GUI tests;
- developer acceptance checks for animation behavior.

They verify that a concrete visual scenario can be launched, observed, and
completed in the actual runtime.

## Activity Sandbox

The universal entry point for activity dev tests is:

```powershell
& ".\.venv\Scripts\python.exe" -m tools.activity_sandbox <scenario>
```

Current scenarios:

```text
bot_turn
```

The activity sandbox:

1. builds the normal application context;
2. creates the normal `TableScreen`;
3. creates the requested test Activity;
4. injects GUI-side dependencies into the Activity;
5. adds the Activity to the screen;
6. runs the standard `RenderEngine`.

`code_map` remains an inspection tool only. It must not become the runtime
launcher for dev tests.

## Quick Launch

For the bot turn visual scenario:

```powershell
.\bush.bat
```

Optional arguments are passed through to `tools.activity_sandbox bot_turn`:

```powershell
.\bush.bat --duration 0.2
.\bush.bat --no-clear-between-bots
.\bush.bat --bot-hand-id top_player_hand
.\bush.bat --target-slot-id cards_slot_frame
```

## Bot Turn Dev Test

The `bot_turn` scenario validates the `BotTurnActivity` and
`BotCardPlayAction` visual flow.

Scenario order:

```text
for bot_hand_id in bot_hand_ids:
    for slot_card_position in ("first", "second"):
        for target_slot_id in target_slot_ids:
            move next card from bot_hand_id to target_slot_id / slot_card_position
```

The test is designed to validate:

- sequential `BotCardPlayAction` execution;
- movement from bot hand frames to table slot frames;
- removal of generated visual cards from bot hands;
- commit of visual card resources into slot activities;
- repeated writes into first and second slot positions;
- behavior across multiple bot hands.

## Expected Result

The GUI window opens and the scenario starts automatically.

For each configured bot hand:

1. table slots are cleared according to scenario options;
2. first cards are moved into all target slots;
3. second cards are moved into all target slots;
4. the next bot hand is tested.

The scenario passes as a manual smoke test if:

- the window opens without runtime exceptions;
- cards visibly move from bot hands to table slots;
- actions run sequentially without overlapping incorrectly;
- every target slot receives the expected first/second visual card;
- source hand visuals shrink as cards are played;
- no stale generated groups remain visible after an action commits.

## Failure Evidence

When a dev test fails, record:

- scenario command;
- fixture/config values used;
- observed behavior;
- expected behavior;
- whether the failure is in Activity orchestration, Action movement, slot commit,
  hand cleanup, layout, or rendering;
- screenshot or short screen recording when possible.

Use concrete terms:

```text
Action did not finish
source group was not removed
target slot did not receive resource key
slot first/second position was overwritten incorrectly
movement target was calculated from wrong coordinate space
```

Avoid vague reports such as:

```text
animation is broken
cards are wrong
GUI glitches
```

## Validation Reporting

Dev test validation should be reported separately from automated checks:

```text
Automated checks:
- py_compile passed through the project .venv with elevated access.
- git diff --check passed; only LF/CRLF warnings.

Dev test:
- .\bush.bat launched bot_turn activity sandbox.
- Result: observed manually; issues recorded separately.
```
