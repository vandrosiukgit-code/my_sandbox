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

Several slot/render-path regressions are now covered by automated tests and
must be treated as contract checks rather than manual-only behavior.

## Test Type

In QA terminology, these scenarios are closest to:

- manual smoke tests;
- exploratory visual tests;
- scenario-based GUI tests;
- developer acceptance checks for animation behavior.

They verify that a concrete visual scenario can be launched, observed, and
completed in the actual runtime.

## Action Runner

The entry point for visual Action dev tests is:

```powershell
& ".\.venv\Scripts\python.exe" fixtures\action_runner.py <command>
```

From bash on Windows, run the same harness from the repository root with:

```bash
./.venv/Scripts/python.exe fixtures/action_runner.py <command>
```

If Git Bash does not resolve the relative `.venv` path, use the absolute
Windows path:

```bash
"C:/Users/Zver/Documents/Codex/2026-04-26/Sandbox/.venv/Scripts/python.exe" fixtures/action_runner.py <command>
```

Current actions:

```text
bot_turn
player_card_play
start_game
table_deal_cards
take_table
discard_table
auto_game
auto_game_full_flow
```

The action runner:

1. builds a controlled visual scene without starting `main.py`;
2. creates the requested test Action;
3. injects GUI-side dependencies into the Action owner;
4. runs the standard `RenderEngine`.

`code_map` remains an inspection tool only. It must not become the runtime
launcher for dev tests.

## Quick Launch

```powershell
& ".\.venv\Scripts\python.exe" fixtures\action_runner.py
```

```bash
./.venv/Scripts/python.exe fixtures/action_runner.py
```

The interactive prompt shows available actions and commands:

```text
list
help
help player_card_play
help 1
run player_card_play
run 1
reload
quit
```

`run 7` launches the automatic game directly on `TableScreen`.
`run 8` launches the same automatic game through the settings screen and then
transitions to the end-game statistics screen.

In interactive mode, `run ...` starts the Pygame action in a separate process
and keeps the prompt available. `reload` stops the current action process and
starts the last `run ...` command again. Use it after adjusting fixtures or
code.

Commands can still be run directly without entering the prompt:

```powershell
& ".\.venv\Scripts\python.exe" fixtures\action_runner.py run player_card_play
```

```bash
./.venv/Scripts/python.exe fixtures/action_runner.py run player_card_play
```

## Player Card Play Dev Test

The `player_card_play` action validates the `PlayerCardPlayAction` visual
flow.

The test is designed to validate:

```text
bottom_player_hand generated card
    -> PlayerCardPlayAction flight group
    -> target slot
    -> slot commit
```

- `PlayerCardPlayAction` execution;
- movement from lower player hand geometry to target slot geometry;
- cleanup of the temporary flight group;
- commit of visual card resources into slot activities.

## Expected Result

The GUI window opens and the scenario starts automatically.

The configured lower-player card moves into the target slot.

The scenario passes as a manual smoke test if:

- the window opens without runtime exceptions;
- the card visibly moves from the lower player hand to the target slot;
- the action finishes;
- the target slot receives the expected visual card;
- no stale flight group remains visible after the action commits.

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
flight group was drawn under settled slot card
slot draw order ignored first-card-under-second-card rule
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
- fixtures\action_runner.py launched player_card_play action sandbox.
- Result: observed manually; issues recorded separately.
```

## Automated Slot/Render Contracts

The following automated suites now lock the table-slot rendering contract:

```text
tests.test_table_slot_visual_order
tests.test_generated_group_lifecycle
tests.test_play_area_slots_activity_transfers
tests.test_bot_turn_activity_sequence
tests.test_card_visibility_behavior
tests.test_first_playable_assembly
```

In particular, the following rule is no longer a manual-only expectation:

```text
When a table slot contains two cards,
the first card stays visually below the second card.
```

The player-turn path also has a separate transient rule:

```text
During the final flight phase,
the moving player card is drawn above already settled slot cards
until commit completes.
```
