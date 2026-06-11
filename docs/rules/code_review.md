# Code Review Guide

## Purpose

Use this document when reviewing code in **The Fool's Reef**.

A review must focus on correctness, architecture boundaries, data flow, lifecycle, coordinate systems, and hidden coupling. Style comments are secondary.

---

## 1. Review mode rules

- Do not edit files unless the user explicitly asks for fixes.
- Use `code_map` before reading large Python files.
- Review the smallest relevant scope first.
- Do not repeat issues already covered by existing reports unless the current file adds new evidence.
- Separate critical architecture deviations from minor code style issues.
- Prefer concrete findings with file/class/function names.
- Avoid generic advice.

---

## 2. Required first checks

Before reviewing a large Python file:

```powershell
& ".\.venv\Scripts\python.exe" -m code_map map <python_file>
```

For multi-file class/module relationships:

```powershell
& ".\.venv\Scripts\python.exe" -m code_map class-diagram <path>
```

For facade-like public classes:

```powershell
& ".\.venv\Scripts\python.exe" -m code_map facade-audit <python_file> --symbol <ClassName> --callers <path> [<path> ...]
```

For protocols, bridges, or public API surfaces:

```powershell
& ".\.venv\Scripts\python.exe" -m code_map protocol-audit <path> [--symbol <ClassName>]
```

If `code_map` fails, mention the failure and continue with direct inspection.

---

## 3. Severity levels

### Critical

A finding is critical if it violates a core architecture boundary or can corrupt lifecycle/data flow.

Examples:

- Game rules move into `Activity`, `Action`, `Group`, `Frame`, or `RenderEngine`.
- `Activity` becomes a screen-level orchestrator.
- Visual `Group` is used as a game entity.
- Internal structures are mutated directly instead of through public APIs.
- Screen-space geometry becomes a second source of truth.
- Input flow bypasses `GameScreen -> GameController`.
- Output flow bypasses `VisualCommand -> GameScreen`.
- A screen-owned `Activity` is started/finished by another `Activity` without explicit ownership.
- Generated visual groups are not cleaned up by their owner.

### High

- Ambiguous local/screen/scaled coordinate use.
- Missing lifecycle/cancel/finish semantics.
- `Action` becomes a long-lived mode.
- Raw pygame events leak too deep into visual behavior code.
- `Group` layer internals are mutated directly.
- Layout is not invalidated after relevant state changes.
- Move animations do not resolve final screen position back to local geometry.

### Medium

- Fixture dictionaries become untyped bags of unrelated parameters.
- Missing validation for scale, angles, counts, positions, or resource keys.
- Debug/runtime paths are mixed.
- Weak public contracts between classes.
- Methods have unclear side effects.
- Dead code or unused parameters confuse the intended design.

### Low

- Missing type hints in stable helper functions.
- Minor naming inconsistencies.
- Comments describe future plans but not current contracts.
- Duplicate small helpers such as easing or interpolation.

---

## 4. Architecture review checklist

### Game logic boundary

Check:

- `GameController` owns rules and logical game state.
- `GameController` does not import pygame.
- `GameController` does not depend on `Group`, `Frame`, `Activity`, or `Action`.
- Visual classes do not decide game legality, turn progression, or card meaning.

Red flags:

```text
selected_group means selected card
Activity starts player turn directly
double_click inside Activity means play card
Group object is passed to controller as game data
```

### GameScreen boundary

Check:

- `GameScreen` owns screen-level orchestration.
- `GameScreen` owns frames, active group IDs, active activities, active actions, input routing, and visual command dispatch.
- `Activity` does not mutate screen registries directly.

Red flags:

```text
screen.screen_frames.pop(...)
screen.active_activities.remove(...)
screen.hand_activities[...] = ...
Activity creates/removes Frame directly
Activity registers another independent Activity directly
```

### Activity boundary

Check:

- `Activity` represents a long-lived visual behavior mode.
- `Activity` may own generated visual-only groups created by itself.
- `Activity` may start short `Action` objects for local visual behavior.
- `Activity` reports completion instead of changing game state directly.

### Action boundary

Check:

- `Action` is short and finite.
- `Action` has clear finish/cancel semantics.
- `Action` changes only allowed visual state.
- `Action` does not decide game meaning.

### Group boundary

Check:

- `Group` remains passive.
- External code does not mutate layer internals.
- External code uses explicit APIs for position, scale, hit rect, layer frames, current frame, text/resource replacement.

Red flags:

```text
group.layers[0]
group.layers[index].frames = ...
Group imports ResourceManager
Group starts animation
Group contains game-rule decisions
```

### Frame boundary

Check:

- `Frame` owns local geometry and child placement.
- External code uses public APIs for placing groups/frames.
- Frame does not know game rules.

Red flags:

```text
frame.group_origins[...] = ...
frame.child_frames.pop(...)
manual parent/child registry edits
screen/local conversion done outside Frame API
```

---

## 5. Coordinate review checklist

Every coordinate method must make these facts clear:

```text
screen-space or parent-local?
scaled or unscaled?
base layout position or animated visual position?
pygame.Rect write or temporary float calculation?
```

Preferred names:

```text
*_local_rect
*_screen_rect
*_scaled_local_rect
local_to_screen
screen_to_local
resolve_screen_position_to_local
```

Ambiguous names must be clarified:

```text
calculate_rect
get_position
set_position
get_slot_content_rect
calculate_fan_rect
```

---

## 6. Input/output review checklist

Expected input path:

```text
pygame event
    -> GameScreen.build_input_event()
    -> GameScreen.hit_test()
    -> ScreenInputEvent
    -> GameController.handle_input()
```

Expected output path:

```text
GameController.handle_input()
    -> VisualCommand objects
    -> GameScreen.dispatch_visual_command()
    -> GuiManifest target/activity resolution
    -> GroupStore / Activity / Action
    -> GameScreen.draw()
```

Check:

- `ScreenInputEvent` describes visual facts only.
- `Activity` does not decide game meaning from click/double-click.
- Controller/settings code uses public GUI targets where possible.

---

## 7. Generated visual groups checklist

Generated visual groups are allowed when they are visual projections of controller data.

Check:

- The creating `Activity` owns them.
- They do not create/delete/mutate game entities.
- They are placed in an assigned `Frame`.
- They are cleaned up when the owning `Activity` finishes.
- They are not drawn twice.

Preferred draw rule:

```text
If generated groups are registered in Frame, Frame/GameScreen draws them.
Activity updates placement/state but does not call group.draw(screen).
```

---

## 8. Review output format

Use this structure:

```markdown
# Review: <file or feature>

## Summary

One paragraph.

## Critical issues

1. ...

## High priority issues

1. ...

## Medium priority issues

1. ...

## Low priority issues

1. ...

## Recommended next steps

1. ...
```

Each issue should include:

```text
file/class/function
what is wrong
why it matters
how to fix it
```

Avoid vague comments such as "needs refactoring" or "could be cleaner".
