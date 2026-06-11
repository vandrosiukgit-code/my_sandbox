# Architecture Checklist

## Purpose

Use this checklist before and after architecture-sensitive changes in **The Fool's Reef**.

This checklist is derived from the project architecture docs and audit findings.

---

## 1. Core roles

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

## 2. Critical boundary checklist

### GameController

- [ ] Owns game rules and logical state.
- [ ] Does not import pygame.
- [ ] Does not depend on `Group`, `Frame`, `Activity`, or `Action`.
- [ ] Receives normalized input facts, not raw visual objects.
- [ ] Emits decisions/commands, not direct visual mutations.

### RenderEngine

- [ ] Owns pygame init/display/event loop/clock/flip only.
- [ ] Does not contain game logic.
- [ ] Does not own screen-level activity orchestration.
- [ ] Does not interpret game input meaning.

### GameScreen

- [ ] Owns screen-level orchestration.
- [ ] Owns frame tree for this screen.
- [ ] Owns active group IDs.
- [ ] Owns active activities/actions.
- [ ] Normalizes input into `ScreenInputEvent`.
- [ ] Dispatches `VisualCommand`.
- [ ] Maps public manifest terms to concrete visual behavior.
- [ ] Does not implement game rules.

### Activity

- [ ] Represents a long-lived visual behavior mode.
- [ ] Does not decide game rules.
- [ ] Does not mutate `GameController`.
- [ ] Does not create/delete `Frame` directly.
- [ ] Does not register/unregister independent screen-level Activity directly.
- [ ] Owns only generated visual-only groups it creates.
- [ ] May start short local `Action` objects.
- [ ] Reports completion to `GameScreen`.

### Action

- [ ] Is short and finite.
- [ ] Has clear finish semantics.
- [ ] Has cancel semantics if it can be interrupted.
- [ ] Changes only allowed visual state.
- [ ] Does not decide game meaning.
- [ ] Does not become a long-lived interaction mode.

### Group

- [ ] Is passive.
- [ ] Has explicit APIs for position, scale, hit rect, layer frames, text/resource replacement.
- [ ] Does not load resources by itself.
- [ ] Does not animate itself.
- [ ] Does not know game rules.
- [ ] External code does not mutate `group.layers[0]`.

### Frame

- [ ] Owns local coordinate system.
- [ ] Owns child frame placement.
- [ ] Owns group placement.
- [ ] Provides local/screen conversion.
- [ ] Does not contain game rules.
- [ ] External code does not mutate `frame.child_frames` or `frame.group_origins`.

---

## 3. Forbidden internals checklist

No new code should directly mutate:

```text
screen.screen_frames
screen.active_activities
screen.hand_activities
frame.child_frames
frame.group_origins
group.layers[0]
```

If direct mutation seems necessary:

1. stop;
2. identify the owner object;
3. add or use a public method;
4. keep the method minimal and named by action.

---

## 4. Coordinate checklist

Coordinate hierarchy:

```text
Screen coordinates
    Frame local coordinates
        nested Frame local coordinates
            Group local coordinates
                Layer local coordinates
```

Check:

- [ ] `Frame.local_rect` is parent-local.
- [ ] `Group.local_rect` is parent-frame-local.
- [ ] `rect` / `hit_rect` are derived screen-space projections.
- [ ] Screen-space geometry is not durable source of truth.
- [ ] Local positions and sizes stay unscaled.
- [ ] Scale is applied during projection/draw according to the docs.
- [ ] Values written into `pygame.Rect`, fixture positions, layer positions, blit positions, or scaled surface sizes are rounded to ints.
- [ ] Any method accepting/returning coordinates states coordinate space in name or docstring.

Preferred names:

```text
*_local_rect
*_screen_rect
*_scaled_local_rect
local_to_screen
screen_to_local
resolve_screen_position_to_local
```

---

## 5. Screen-space movement checklist

Screen-space movement is allowed only as temporary animation convenience.

Check:

- [ ] The movement is owned by `Action`.
- [ ] The target group is still alive/registered while action runs.
- [ ] The final screen position is resolved back into local rect relative to the current or new parent `Frame`.
- [ ] Screen-space position is not stored as second durable state.
- [ ] If parent frame changes, reparenting/local resolution is explicit.

---

## 6. Input flow checklist

Expected input path:

```text
pygame event
    -> GameScreen.build_input_event()
    -> GameScreen.hit_test()
    -> ScreenInputEvent
    -> GameController.handle_input()
```

Check:

- [ ] Raw pygame event does not reach game logic.
- [ ] `ScreenInputEvent` is a visual fact only.
- [ ] `Activity` does not decide game meaning from click/double-click.
- [ ] Visual `Group` is translated to `group_id`.
- [ ] If needed, `group_id` is mapped to `card_id` / `hand_index` before game decision.
- [ ] `GameController` decides legality and meaning.

---

## 7. Output flow checklist

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

- [ ] Public GUI targets are used where possible.
- [ ] Controller/settings code does not know internal group/layer details.
- [ ] Visual commands are dispatched by `GameScreen`.
- [ ] Stable visual modes map to `Activity`.
- [ ] Short visual steps map to `Action`.
- [ ] `GroupStore` handles configured group resource/text updates.

---

## 8. GuiManifest checklist

Check:

- [ ] Public target IDs are stable.
- [ ] Public target IDs are unique.
- [ ] Player target IDs are side-specific.
- [ ] Target names expose stable GUI concepts, not internal implementation details.
- [ ] `GroupStore.apply_target_value()` or equivalent handles supported target types.
- [ ] `assets/gui_manifest.json`, if present, is treated as generated/snapshot artifact, not source of truth.

---

## 9. Generated visual groups checklist

Generated visual-only groups are allowed when they are screen representations of controller data.

Check:

- [ ] Created by the owning `Activity`.
- [ ] Owned and cleaned up by the creating `Activity`.
- [ ] Placed inside assigned `Frame`.
- [ ] Built from injected resources/resource keys.
- [ ] Do not create/delete/mutate game entities.
- [ ] Do not become game identity.
- [ ] Drawn by a single owner.

Recommended draw rule:

```text
If generated groups are registered in Frame, Frame/GameScreen draws them.
Activity updates placement/state but does not call group.draw(screen).
```

---

## 10. Activity ownership checklist

If an `Activity` receives another `Activity` instance:

- [ ] Ownership is explicit.
- [ ] It does not finish externally owned Activity.
- [ ] It does not start already-started long-lived Activity without checking lifecycle.
- [ ] It does not remove externally owned Activity from screen registries.
- [ ] Child ownership is documented in constructor or class docstring.

Recommended rule:

```text
Activity owns only child actions or generated visual-only groups that it created.
Screen-owned Activity lifecycle belongs to GameScreen.
```

---

## 11. Action / Animation checklist

Check:

- [ ] Project-level orchestration uses `Action`, not raw `Animation`, where possible.
- [ ] `Animation` remains a low-level interpolation primitive.
- [ ] `Action` owns its animation primitive.
- [ ] Finish/cancel behavior is explicit.
- [ ] Reuse semantics are clear: one-shot or resettable.
- [ ] Conflicting visual properties are handled or documented.
- [ ] Deleted/unregistered groups are not updated.

---

## 12. Resource injection checklist

Check:

- [ ] `ResourceManager` is the only source of raw graphical data.
- [ ] `Group` does not fetch resources by itself.
- [ ] `Activity` receives resources/resource keys through constructor/config/command.
- [ ] Runtime visual objects do not hardcode asset loading.

---

## 13. Fixture/config checklist

Check:

- [ ] Fixture keys are documented or converted into typed config.
- [ ] Partial fixture updates do not accidentally wipe defaults.
- [ ] Values are validated: counts, scale, angles, positions, resource keys.
- [ ] Debug-only fixture paths do not become runtime contracts.
- [ ] Runtime data should come from `GameController` / view model, not debug manifests.

---

## 14. Validation checklist

After code changes:

- [ ] Run targeted tests if available.
- [ ] Run syntax check for changed Python files:

```powershell
& ".\.venv\Scripts\python.exe" -m py_compile <changed_file.py>
```

- [ ] If `py_compile` or `code_map` fails with `No Python at ...` or another
      sandbox-related access error, rerun the same command with elevated access.
- [ ] Do not describe this project case as a broken `.venv`; normal sandbox
      execution cannot access the venv base interpreter outside the workspace.
- [ ] Run relevant smoke script if applicable.
- [ ] Confirm no forbidden internals were newly mutated.
- [ ] Confirm coordinate names remain explicit.
- [ ] Confirm no architecture boundary was crossed.
- [ ] If validation cannot be run, record why.

---

## 15. Architecture review summary template

```markdown
## Architecture check summary

### Preserved boundaries

- ...

### Deviations found

- Critical: ...
- High: ...
- Medium: ...

### Required fixes

1. ...

### Validation

- ...
- Python checks must use the canonical environment wording from `AGENTS.md`.
```

Do not hide architecture deviations under generic refactor language.
