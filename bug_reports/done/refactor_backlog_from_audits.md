# Refactor backlog from bug reports

Backlog built from the audit reports in `bug_reports/`.

Primary goal:

```text
stabilize GUI architecture before connecting real GameController rules
```

Do not start from cosmetic cleanup. First remove ownership ambiguity and unsafe
state mutation, then fix coordinate and animation contracts.

---

# P0. Stop Direct Internal Mutations

## P0.1. Add public APIs for screen registries

Problem:

Code mutates `screen.screen_frames`, `screen.active_activities`,
`screen.hand_activities`, and similar registries directly.

Tasks:

- Add explicit `GameScreen` APIs for frame creation, lookup, removal, and child-frame registration.
- Add explicit `GameScreen` APIs for activity add/remove/lookup.
- If `hand_activities` remains, hide it behind public methods.
- Replace direct mutations in activities with those APIs.

Acceptance criteria:

- No production code outside `GameScreen` writes to `screen.screen_frames`.
- No production code outside `GameScreen` writes to `screen.active_activities`.
- Removing a frame/activity updates all relevant registries consistently.

## P0.2. Add public APIs for Frame internals

Problem:

Activities mutate `frame.child_frames`, `frame.group_origins`, and group lists
directly.

Tasks:

- Add `Frame.add_child_frame()`, `Frame.remove_child_frame()`, `Frame.has_child_frame()`.
- Add `Frame.place_group_local()` / `Frame.move_group_local()` or equivalent.
- Add `Frame.remove_group_id()` with origin cleanup.
- Replace direct `child_frames` and `group_origins` mutations.

Acceptance criteria:

- No production code outside `Frame` writes to `frame.child_frames`.
- No production code outside `Frame` writes to `frame.group_origins`.
- Group placement and origin updates happen through one path.

## P0.3. Add public APIs for Group layer mutation

Problem:

Code reads or writes `group.layers[0]` and stores temporary state directly on
`Group`.

Tasks:

- Add explicit layer lookup/update APIs on `Group`.
- Add APIs for replacing layer resource/frames.
- Move rest-state, slot metadata, and selection metadata out of `Group` where possible.
- Replace direct `group.layers[0]` usage.

Acceptance criteria:

- No production code outside `Group` accesses `group.layers[index]`.
- Visual state owned by activities is stored in activity-owned structures, not ad hoc group attributes.

---

# P1. Clarify GameScreen / Activity / GameController Responsibilities

## P1.1. Move screen-level orchestration back to GameScreen

Problem:

Some activities create/remove frames, start/register other activities, and act
as partial screen orchestrators.

Tasks:

- Identify all activity code that creates/removes frames.
- Move frame lifecycle ownership to `GameScreen`.
- Keep activities focused on visual behavior inside assigned frames.
- Convert `PlayAreaSlotsActivity` from screen orchestrator to layout/activity helper or split it.

Acceptance criteria:

- Activities do not directly create/delete screen frames.
- Activities do not directly register/unregister independent screen-level activities.
- `GameScreen` remains the owner of screen registries and lifecycle.

## P1.2. Make nested Activity ownership explicit

Problem:

Activities call `start()` / `finish()` on other activities without clear
ownership.

Tasks:

- Add explicit ownership flags or ownership documentation for injected activities.
- Ensure an activity only finishes child activities it created or explicitly owns.
- Make `CardSelectionActivity`, `PlayerTurnActivity`, and decorators follow the same rule.

Acceptance criteria:

- Finishing card selection does not accidentally destroy a long-lived hand activity.
- Finishing a player turn does not accidentally destroy persistent play-area slot state.
- Ownership behavior is visible in constructor arguments or class contract.

## P1.3. Route game decisions through GameController

Problem:

Visual `Group` objects are used as selected game cards.

Tasks:

- Define stable game identifiers for selection: `card_id`, `hand_index`, `player_id`.
- Add mapping from visual `group_id` to game identifier in the visual layer.
- Send normalized input facts to `GameController`.
- Return `VisualCommand` objects for visual reactions.
- Stop passing `Group` as selected-card data.

Acceptance criteria:

- GameController receives stable game identifiers, not `Group` objects.
- Card selection can survive visual group recreation.
- Double-click meaning is decided by controller or a controller-facing command layer.

---

# P2. Fix Coordinate-Space Contract

## P2.1. Name coordinate spaces explicitly

Problem:

Reports show repeated confusion between local, screen, scaled, and content
rects.

Tasks:

- Audit public methods that accept/return positions or rects.
- Rename ambiguous APIs or update docstrings to state coordinate space.
- Standardize names such as `local_rect`, `screen_rect`, `scaled_local_rect`,
  `local_to_screen`, `screen_to_local`.

Acceptance criteria:

- Any method moving or measuring a group/frame states its coordinate space.
- New code does not use ambiguous names like `rect` for input parameters without clarification.

## P2.2. Define one source of truth for layout geometry

Problem:

Screen-space geometry and local geometry can diverge during layout or animation.

Tasks:

- Decide which object owns base local layout for groups inside frames.
- Ensure screen-space values are derived projections.
- Update placement APIs so local state and derived screen state stay synchronized.
- Ensure final animation positions resolve back to local geometry when needed.

Acceptance criteria:

- Frame-local geometry is the persistent layout source of truth.
- Screen-space movement does not permanently fork layout state.
- `frame.group_origins` or its replacement cannot become stale after movement.

## P2.3. Fix slot and hand coordinate calculations

Problem:

Slot and hand activities mix scaled bounds, local rects, screen rects, and
derived positions.

Tasks:

- Audit `CardsSlotActivity` slot content normalization.
- Audit `PlayAreaSlotsActivity` play-area local vs screen calculations.
- Audit `BotHandActivity` and `PlayerHandActivity` local/screen usage.
- Add focused regression checks for representative hand/slot layouts.

Acceptance criteria:

- Slot content bounds and group positions are computed in a documented coordinate space.
- Layout remains correct after update/re-layout.
- Hit detection uses geometry consistent with what is drawn.

---

# P3. Stabilize Card Transform Pipeline And Animation Lifecycle

## P3.1. Fix card transform pipeline

Problem:

`BotHandActivity.apply_card_transform()` combines surface rotation, group scale,
local scale, pivot math, and drawing ownership. `PlayerHandActivity` inherits
these risks.

Tasks:

- Decide where rotation, scale, and pivot transforms belong.
- Separate layout transform from rendered transform.
- Fix or verify pivot angle sign.
- Remove double-draw risk between Frame and activity draw paths.
- Ensure `PlayerHandActivity` does not inherit invalid bot-specific assumptions.

Acceptance criteria:

- A generated card group is drawn by exactly one owner.
- Transform math has one documented pipeline.
- Player hand and bot hand can diverge without hidden coupling.

## P3.2. Separate Action and Animation roles

Problem:

Animation and Action responsibilities overlap.

Tasks:

- Define `Action` as finite visual step owned by activity/frame.
- Define lower-level animation primitive, if still needed.
- Decide whether animation instances are one-shot or reusable.
- Add `cancel()` semantics.
- Add conflict handling at least at activity level.

Acceptance criteria:

- A running visual step has clear start/update/finish/cancel behavior.
- Reusing an animation cannot accidentally reuse stale start position/scale.
- Two animations cannot unknowingly fight over the same group property.

## P3.3. Separate local-position and screen-position animations

Problem:

Animation reports identify mixed local/screen position semantics.

Tasks:

- Split or explicitly tag local-position vs screen-position animation classes.
- Validate position inputs.
- Decide whether interpolation uses float internally and integer projection at write time.
- Ensure animation completion synchronizes layout state when required.

Acceptance criteria:

- Animation class names or constructor arguments identify coordinate space.
- Final state after animation is consistent with frame/group layout.

---

# P4. Runtime Safety And Validation

## P4.1. Harden RenderEngine lifecycle

Problem:

Runtime loop cleanup and screen lifecycle are minimal.

Tasks:

- Wrap run loop in `try/finally` so `pygame.quit()` always runs.
- Add screen `start()` / `finish()` or equivalent lifecycle contract.
- Make event return semantics explicit.
- Add `target_fps` and `max_dt`.
- Decide whether engine or screen clears the display.

Acceptance criteria:

- Runtime cleanup happens after exceptions.
- Screen startup/shutdown behavior is explicit.
- Large `dt` spikes are capped or handled deliberately.

## P4.2. Validate externally supplied configuration

Problem:

Fixtures and runtime config accept invalid ratios, offsets, counts, scales, and
card lists.

Tasks:

- Validate scale factors, angles, ratios, slot counts, card counts, offsets.
- Decide when bad input should raise versus be clamped.
- Make silent truncation/ignore behavior explicit.

Acceptance criteria:

- Invalid fixture/config data fails predictably.
- Layout code does not produce impossible geometry from unchecked input.

---

# P5. Maintainability Cleanup

## P5.1. Add Protocols and type hints at boundaries

Tasks:

- Add Protocols for activity-like, hand-activity-like, frame-like, and group-like collaborators.
- Type public methods changed in P0-P4.
- Prefer dataclasses for structured geometry results over loose dicts.

Acceptance criteria:

- Public contracts are visible without reading implementation internals.
- Common wiring mistakes fail earlier.

## P5.2. Rename methods with hidden side effects

Tasks:

- Rename methods such as `normalize_*` when they mutate state.
- Document remaining side-effecting methods.

Acceptance criteria:

- Method names distinguish pure calculation from mutation.

## P5.3. Separate debug/dev behavior from runtime behavior

Tasks:

- Identify debug-only drawing, fixture shortcuts, and temporary scaffolds.
- Gate debug behavior behind explicit flags or dev-only paths.

Acceptance criteria:

- Runtime code path is not dependent on debug scaffolding.

---

# Recommended Execution Order

1. P0.1, P0.2, P0.3.
2. P1.1 and P1.2.
3. P1.3.
4. P2.1 and P2.2.
5. P2.3.
6. P3.1.
7. P3.2 and P3.3.
8. P4.
9. P5.

Do not start broad type-hinting or naming cleanup before P0-P2 are stable.
