# AGENTS.md

## Python environment

This project uses the PyCharm virtual environment:

```text
C:/Users/Zver/Documents/Codex/2026-04-26/Sandbox/.venv/Scripts/python.exe
```

On Windows PowerShell, do not rely on bare `python`, `py`, or virtualenv activation.

Prefer explicit interpreter calls:

```powershell
& ".\.venv\Scripts\python.exe" --version
& ".\.venv\Scripts\python.exe" -m pip --version
& ".\.venv\Scripts\python.exe" -m py_compile <changed_file.py>
```

Codex sandbox note:

The virtual environment is valid on the host machine, but normal sandboxed
execution may fail because `.venv\Scripts\python.exe` resolves its base
interpreter outside the workspace:

```text
C:\Users\Zver\AppData\Local\Programs\Python\Python311\python.exe
```

If an explicit `.venv\Scripts\python.exe` command fails with `No Python at ...`
or another sandbox-related access error, rerun the same check with elevated
access instead of treating the virtual environment as broken.

Do not describe this as a broken `.venv` in validation reports. The correct
description is:

```text
Normal sandbox execution of .\.venv\Scripts\python.exe is unavailable because
the venv resolves its base interpreter outside the workspace. The same check
must be rerun with elevated access.
```

Allowed elevated command categories for this project:

```powershell
& ".\.venv\Scripts\python.exe" -m py_compile ...
& ".\.venv\Scripts\python.exe" -m unittest ...
& ".\.venv\Scripts\python.exe" -m code_map ...
```

Keep elevated requests narrow. Do not request broad approval for arbitrary
`python`, `py`, or generic PowerShell execution.

Do not run:

```powershell
python ...
py ...
.\.venv\Scripts\Activate.ps1
```

unless the user explicitly asks to debug shell activation.

If the explicit interpreter path still fails after the allowed elevated retry,
stop and report the exact error instead of trying random Python installations.

Validation wording for Python checks:

```text
py_compile passed through the project .venv with elevated access.
```

or, if the elevated retry was not approved or still failed:

```text
py_compile was not completed. Normal sandbox execution of .\.venv\Scripts\python.exe
cannot access the venv base interpreter outside the workspace: <exact error>.
```

---

## 1. Project role

Codex works on **The Fool's Reef**, a Pygame card-game GUI project with a data-first visual architecture.

Codex must preserve the documented architecture and treat documentation as the intended direction when code and docs disagree.

General behavior, token economy, duplicate-work prevention, response style, safety rules, and generic editing discipline are defined in Global Codex Instructions and must not be duplicated here.

This file contains only project-specific rules.

---

## 2. Sources of truth

Read relevant docs before architecture-sensitive changes:

```text
docs/architectural_manifesto_v6.2.md
docs/architecture.md
docs/current_architecture_snapshot.md
docs/dev_tests.md
docs/gui_manifest.md
docs/screen_layout_refactor_backlog.md
docs/visual_input_flow.md
```

Project rule documents:

```text
docs/rules/code_review.md
docs/rules/refactor_rules.md
docs/rules/architecture_checklist.md
```

Use them as task-specific guidance:

- for code review, follow `docs/rules/code_review.md`;
- for refactoring, follow `docs/rules/refactor_rules.md`;
- before and after architecture-sensitive changes, follow `docs/rules/architecture_checklist.md`.

Architecture audit references, if present:

```text
docs/project_architecture_alignment_report.md
docs/activity_architecture_audit_report.md
docs/animations_architecture_audit_report.md
```

Runtime/config sources:

```text
group_config.json
assets/resource_manifest.json
```

Rule:

```text
Documentation describes the intended architecture.
If code and documentation disagree, report the deviation before changing behavior.
```

---

## 3. Code navigation

Use the local `code_map` tool as the first-pass navigation tool before reading large Python files.

Preferred commands on Windows PowerShell:

```powershell
& ".\.venv\Scripts\python.exe" -m code_map map <python_file>
& ".\.venv\Scripts\python.exe" -m code_map class-diagram <path> [output.puml]
& ".\.venv\Scripts\python.exe" -m code_map facade-audit <python_file> --symbol <ClassName> --callers <path> [<path> ...]
& ".\.venv\Scripts\python.exe" -m code_map protocol-audit <path> [--symbol <ClassName>]
```

Rules:

- Run `code_map map <file>` before reading a large Python file.
- Use `class-diagram` before broad multi-file architecture refactors.
- Use `facade-audit` before changing facade-like public classes.
- Use `protocol-audit` before changing protocols, bridges, or public API surfaces.
- `code_map` is an inspection tool, not a replacement for reading the exact code that will be changed.
- If `code_map` fails, mention the failure and fall back to direct inspection.

Prefer repository-relative paths.

Good:

```powershell
& ".\.venv\Scripts\python.exe" -m code_map map src/activities/bot_hand_activity.py
```

Avoid absolute user-machine paths unless necessary.

---

## 4. Core architecture boundaries

Project roles:

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

Contract hierarchy:

```text
Domain contract      — core/durak only. Game rules, game state, domain actions,
                       domain snapshots, domain events, autonomous session flow.
Adapter contract     — screen-facing translation between domain results and GUI
                       commands. No game rules.
GUI contract         — ScreenInputEvent, ActivityResult, VisualCommand,
                       ControllerResponse. Screen/activity orchestration only.
```

Hard boundaries:

- Game rules belong only to `GameController`.
- `core/durak` is the authoritative domain layer for game rules and full
  autonomous session flow.
- `core/durak` must not import or depend on GUI contracts such as
  `ScreenInputEvent`, `ActivityResult`, `VisualCommand`, or
  `ControllerResponse`.
- `core/game_controller.py` is a screen-facing adapter layer. It may translate
  between domain results and GUI contracts, but it must not become a second
  rules engine.
- `RenderEngine` must not contain game logic or screen orchestration.
- `GameScreen` owns screen-level orchestration.
- `Activity` must not become a screen orchestrator.
- `Group` must remain passive.
- `Frame` must not contain game rules.
- `Action` must not become a long-lived mode.
- Visual `Group` must not be treated as a game entity.

---

## 5. Forbidden project-specific changes

Do not directly mutate internal structures such as:

```text
screen.screen_frames
screen.active_activities
screen.hand_activities
frame.child_frames
frame.group_origins
group.layers[0]
```

Use or add explicit public APIs instead.

Do not:

- create/delete `Frame` directly inside `Activity`;
- register/unregister independent screen-level `Activity` directly inside another `Activity`;
- pass visual `Group` as selected game card;
- move game decisions into `Activity`;
- import `pygame` or visual classes into `GameController`;
- fetch resources inside `Group` or `Activity` instead of injecting them;
- make screen-space geometry a second source of truth.

---

## 6. Activity / Action / Group / Frame rules

### Activity

Allowed:

- own generated visual-only groups created by itself;
- update visual behavior inside its assigned `Frame`;
- start short `Action` objects for local visual behavior;
- report completion to `GameScreen`.

Not allowed:

- decide game rules;
- mutate `GameController`;
- create/delete `Frame` directly;
- register/unregister independent screen-level activities directly;
- treat visual groups as game data.

If an `Activity` receives another `Activity` from outside, it must not finish it unless ownership is explicit.

Recommended ownership rule:

```text
An Activity owns only child actions or visual-only groups that it created itself.
Screen-owned activities are started and finished by GameScreen.
```

### Action

`Action` is a short finite visual step.

It may move, scale, flip, or visually update a `Group`.

It must have clear finish/cancel semantics.

Animation primitives may exist inside Action, but project-level orchestration should operate through Action.

### Group

`Group` is passive.

Use explicit APIs for:

```text
position
scale_factor
hit_rect
layer frames
layer current frame
text/resource replacement
```

Do not mutate layer internals directly.

### Frame

`Frame` owns local geometry, child frames, and group placement.

External code must use public APIs to add/remove/place groups or child frames.

---

## 7. Coordinate contract

Coordinate hierarchy:

```text
Screen coordinates
    Frame local coordinates
        nested Frame local coordinates
            Group local coordinates
                Layer local coordinates
```

Rules:

- `Frame.local_rect` is parent-local.
- `Group.local_rect` is parent-frame-local.
- `rect` and `hit_rect` are derived screen-space projections.
- Screen-space geometry is not a source of truth.
- Local positions and sizes stay unscaled.
- Scale is applied during projection/draw according to the architecture docs.
- Values written into `pygame.Rect`, fixture positions, layer positions, blit positions, or scaled surface sizes must be integer-rounded.
- Any method that accepts or returns coordinates must make the coordinate space explicit in its name or docstring.

Preferred naming:

```text
*_local_rect
*_screen_rect
*_scaled_local_rect
local_to_screen
screen_to_local
resolve_screen_position_to_local
```

Screen-space movement is allowed only as temporary animation convenience.

At the end of screen-space movement, resolve the final screen position back into local rect relative to the current or new parent `Frame`.

---

## 8. Input / output flow

Domain flow:

```text
External caller / tests / adapter
    -> core/durak domain actions
    -> core/durak controller
    -> domain snapshot + domain events
```

Input path:

```text
pygame event
    -> GameScreen.build_input_event()
    -> GameScreen.hit_test()
    -> ScreenInputEvent
    -> GameController.handle_input()
```

`ScreenInputEvent` is a visual fact, not game meaning.

Output path:

```text
GameController.handle_input()
    -> VisualCommand objects
    -> GameScreen.dispatch_visual_command()
    -> GuiManifest target/activity resolution
    -> GroupStore / Activity / Action
    -> GameScreen.draw()
```

Do not let `Activity` decide game meaning from clicks, double-clicks, hovered groups, or selected visual groups.

Controller/settings code should prefer public GUI targets:

```text
player.left.avatar
player.left.name
table.surface
```

over direct group/layer internals unless low-level visual code is being changed.

Rule:

```text
GUI contracts are adapter-facing only.
They must not become the primary contract for domain rules or autonomous game flow.
```

---

## 9. Project validation checklist

After project code changes, verify the relevant items:

- `GameController` has no `pygame` or visual-object dependency.
- `core/durak` has no dependency on GUI contracts or visual runtime modules.
- `core/game_controller.py` remains a translator, not a second owner of rules.
- `Activity` did not gain game-rule responsibility.
- `Activity` did not become a screen-level registry owner.
- `Action` remains finite.
- `Group` remains passive.
- `Frame` is not mutated through raw internal dictionaries/lists.
- Coordinate-space names are explicit.
- Generated visual groups are owned and cleaned up by their creating `Activity`.
- Screen-space movement resolves back to local geometry.
- Public GUI target names remain stable and unique.

For architecture-sensitive changes, also consult:

```text
docs/rules/architecture_checklist.md
```

For changed Python files, use the project interpreter:

```powershell
& ".\.venv\Scripts\python.exe" -m py_compile <changed_file.py>
```
