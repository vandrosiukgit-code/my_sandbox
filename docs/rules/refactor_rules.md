# Refactor Rules

## Purpose

Use this document when modifying or refactoring code in **The Fool's Reef**.

The goal is to improve the project while preserving its documented architecture.

```text
RenderEngine   — Pygame runtime loop only.
GameController — game rules and logical state.
GameScreen     — active screen orchestrator.
GroupStore     — long-lived configured groups.
Frame          — local coordinate container.
Group          — passive visual object.
Activity       — long-lived visual behavior mode.
Action         — short finite visual step.
GuiManifest    — public visual command/target language.
```

---

## 1. Refactor principles

### Smallest safe change

Prefer the smallest change that solves the requested problem.

Do not rewrite a subsystem when a public API, adapter, or local cleanup is enough.

### Preserve behavior

Do not change visible behavior unless the task explicitly asks for it.

If behavior must change to satisfy the architecture, explain the change before implementing it.

### Preserve architecture

A refactor is not acceptable if it fixes local code by breaking architecture.

Never fix a local bug by:

- moving game rules into visual code;
- making `Activity` a screen orchestrator;
- making `Group` active;
- using screen-space geometry as durable state;
- making screen layout depend on Activity-generated groups or Action-transient
  group positions;
- bypassing `GuiManifest` for public visual commands.

### Prefer existing patterns

Use existing project contracts and naming conventions.

Do not introduce new frameworks, global managers, or abstraction families unless explicitly requested.

---

## 2. Required pre-refactor checks

Before editing:

1. Identify the exact goal.
2. Identify the files likely to change.
3. Run `code_map` for large Python files:

```powershell
& ".\.venv\Scripts\python.exe" -m code_map map <python_file>
```

4. Read the relevant documentation if the change is architecture-sensitive:

```text
docs/architectural_manifesto_v6.2.md
docs/architecture.md
docs/current_architecture_snapshot.md
docs/gui_manifest.md
docs/visual_input_flow.md
```

For multi-file class relationship changes:

```powershell
& ".\.venv\Scripts\python.exe" -m code_map class-diagram <path>
```

For facade-like public classes:

```powershell
& ".\.venv\Scripts\python.exe" -m code_map facade-audit <python_file> --symbol <ClassName> --callers <path> [<path> ...]
```

For protocols/bridges/public API surfaces:

```powershell
& ".\.venv\Scripts\python.exe" -m code_map protocol-audit <path> [--symbol <ClassName>]
```

---

## 3. Hard refactor prohibitions

Do not directly mutate:

```text
screen.screen_frames
screen.active_activities
screen.hand_activities
frame.child_frames
frame.group_origins
group.layers[0]
```

Instead, add or use public APIs.

Do not:

- move game decisions into `Activity`;
- use visual `Group` as selected game card;
- create/delete `Frame` inside `Activity` directly;
- register/unregister independent screen-level `Activity` inside another `Activity`;
- import pygame into `GameController`;
- fetch resources inside `Group` or `Activity` instead of injecting them;
- convert screen-space geometry into durable state;
- add global manager classes to solve local ownership confusion.

---

## 4. Safe refactor patterns

### Replace direct mutation with public API

Bad:

```python
frame.group_origins[group.id] = group.local_rect.topleft
```

Better:

```python
frame.set_group_origin(group.id, group.local_rect.topleft)
```

Bad:

```python
group.layers[0].frames = [surface]
```

Better:

```python
group.replace_layer_frames(layer_name, [surface])
```

Bad:

```python
screen.active_activities.remove(activity)
```

Better:

```python
screen.remove_activity(activity)
```

### Extract coordinate conversion into owner

Bad:

```python
local_x = screen_x - frame.rect.x
```

Better:

```python
local_x, local_y = frame.screen_to_local((screen_x, screen_y))
```

### Move game meaning out of Activity

Bad:

```text
CardSelectionActivity:
    double click -> selected_group -> start player turn
```

Better:

```text
GameScreen:
    hit-test -> ScreenInputEvent

GameController:
    decides selected card / legal action

GameScreen:
    receives VisualCommand and starts Activity/Action
```

### Wrap Animation in Action

Bad:

```text
Activity stores many raw animation objects with unclear finish/cancel policy.
```

Better:

```text
Activity starts CardHoverAction / MoveGroupAction / ScaleGroupAction.
Action owns low-level Animation and has clear finish/cancel semantics.
```

---

## 5. Refactoring Activity

Allowed:

- improve visual layout;
- improve generated visual-only group lifecycle;
- add public configuration methods;
- start or cancel local `Action` objects;
- report completion.

Not allowed:

- decide game rules;
- mutate `GameController`;
- create/delete `Frame` directly;
- mutate screen registries directly;
- finish screen-owned activities unless explicit ownership is present.

When refactoring an `Activity` that wraps another `Activity`, add explicit ownership semantics:

```python
owns_child_activity: bool = False
```

Only finish child activity if ownership is true.

---

## 6. Refactoring Action / Animation

`Action` is project-level architecture.
`Animation` is a low-level interpolation primitive.

When refactoring animations:

- keep `Action` finite;
- add `cancel()` where replacement/hover interruption is possible;
- avoid updating deleted/unregistered groups;
- identify animated properties;
- prevent two actions from fighting over the same visual property where practical;
- ensure screen-space movement resolves back to local geometry at the end.

Do not make `Animation` decide game meaning.

---

## 7. Refactoring Group

`Group` must remain passive.

Safe changes:

- add explicit APIs for visual state changes;
- improve layer access by name;
- improve rect/hit_rect projection;
- improve validation of scale/position/layer names.

Unsafe changes:

- resource loading inside `Group`;
- animation timing inside `Group`;
- game-rule decisions inside `Group`;
- exposing layer internals as the normal write path.

---

## 8. Refactoring Frame

`Frame` owns local coordinate space and child placement.

Safe changes:

- add public APIs for group placement;
- add public APIs for child frame placement;
- improve local/screen conversion;
- improve derived rect/hit_rect projection.

Unsafe changes:

- game rules inside `Frame`;
- direct external mutation of internal lists/dicts;
- hidden screen-level orchestration inside `Frame`.

---

## 9. Refactoring GameScreen

`GameScreen` is the active screen orchestrator.

Safe changes:

- centralize frame/activity/action lifecycle;
- centralize input normalization;
- dispatch `VisualCommand`;
- map public activity/action terms to concrete classes;
- keep active group IDs and screen draw order.
- calculate screen layout from stable `Frame` geometry.

Unsafe changes:

- game rules inside `GameScreen`;
- long complex visual scenario code directly in `GameScreen`;
- bypassing `Activity`/`Action` for stable visual modes;
- bypassing `GuiManifest` for public visual targets.
- layout calculations based on generated groups owned by an Activity;
- layout calculations based on transient positions while an Action is running.

---

## 10. Refactoring RenderEngine

`RenderEngine` owns only runtime loop concerns.

Safe changes:

- target FPS;
- max dt;
- `try/finally pygame.quit()`;
- screen start/finish call;
- passing runtime context to screen factory.

Unsafe changes:

- game rules;
- screen orchestration;
- controller decisions;
- activity/action ownership.

---

## 11. Validation after refactor

Run the smallest relevant checks.

For changed Python files:

```powershell
& ".\.venv\Scripts\python.exe" -m py_compile <changed_file.py>
```

If `py_compile` fails with `No Python at ...` or another sandbox-related access
error, rerun the same command with elevated access. Do not report this as a
broken `.venv`.

Correct wording when the elevated retry passes:

```text
py_compile passed through the project .venv with elevated access.
```

Correct wording when the elevated retry is not approved or still fails:

```text
py_compile was not completed. Normal sandbox execution of .\.venv\Scripts\python.exe
cannot access the venv base interpreter outside the workspace: <exact error>.
```

Architecture-sensitive verification:

- `GameController` has no pygame dependency.
- `Activity` did not gain game-rule responsibility.
- `Activity` did not become screen-level registry owner.
- `Action` remains finite.
- `Group` remains passive.
- `Frame` is not mutated through raw internals.
- Coordinate names remain explicit.
- Generated visual groups are visual-only and cleaned up.
- Screen-space movement resolves back to local geometry.
- Public GUI target names remain stable.

---

## 12. Refactor report format

After refactoring, summarize:

```markdown
## Changed

- file/path.py — short description

## Validation

- command run
- result
- for Python commands, use the project wording above; do not call `.venv` broken

## Architecture notes

- any boundary preserved or repaired
- any remaining risk
```

Do not paste large diffs unless requested.
