# gui_editor.py Working Contract

## Scope

This document defines local rules only for:

```text
tools/gui_editor.py
tests/test_gui_editor.py
```

It does not override broader project architecture for runtime game code.

## Purpose

`gui_editor.py` is a developer tool for fast editing of GUI data structures:

- `GameScreen`
- `Frame`
- `Group`

The tool edits project GUI data. It is not the game runtime and must not absorb
runtime gameplay logic.

## Primary UX model

The editor follows a compact split-view layout:

- left side: authoring forms (`CREATE`, later `EDIT`);
- right side: navigation and inspection (`RM Manifest Explorer`, `GUI Explorer`).

The interface should stay dense, readable, and predictable on a small window.

Compactness means efficient use of space, not maximal packing density.

Rules:

- reduce empty space and irrational width before reducing readability;
- optimize width more aggressively than height;
- if readability conflicts with vertical compactness, readability wins;
- a slightly taller form is acceptable; merged or visually stuck controls are not;
- `CREATE` sections may grow vertically and must not be compressed just to fit
  the viewport without scrolling.

## UI design contract

`CREATE` must not be implemented as a loose collection of controls.
It must follow one explicit composition contract shared by `Screen`, `Frame`,
and `Group`.

### 1. Content-first sizing

- Section height is determined by content.
- Do not force `Screen`, `Frame`, or `Group` panels into arbitrary fixed heights.
- If content does not fit, adjust composition or panel height, not font size.

### 2. One design system

- `Screen`, `Frame`, and `Group` forms must use the same visual rules.
- Identical control roles must have the same typography, input height, spacing,
  button sizing, and status presentation.

### 3. Rational density

- Avoid large empty areas.
- Avoid oversized paddings.
- Prefer compact but readable layouts.

### 4. Form follows data

- Long identifiers may use full-width fields.
- Numeric geometry fields should stay compact.
- Short coordinate and size fields may be grouped in multiple columns.

### 5. Stable hierarchy

- The three authoring zones must read clearly as:
  - `Screen`
  - `Frame`
  - `Group`
- Visual hierarchy must come from structure, spacing, headers, and alignment,
  not from ad hoc decorative elements.

### 5.1. CREATE wireframe contract

Each `CREATE` section must use the same row order:

1. section title
2. section description
3. identity block
4. geometry block, if the entity has geometry fields
5. action row
6. status row

Rules:

- `identity block` uses stacked full-width rows.
- `geometry block` uses a compact two-column grid.
- `action row` contains the primary button on its own row.
- `status row` contains status text on its own row.
- `status row` must never share vertical space with the button row.
- `Screen`, `Frame`, and `Group` must differ by field content only, not by
  layout grammar.

### 6. No overlap

- Buttons, labels, fields, and status messages must never overlap.
- Controls must fit naturally within their section.

### 7. Native toolkit behavior first

- Prefer standard `PySide6` widgets, layout behavior, and styling hooks.
- Do not replace native layout behavior with custom geometry code unless there is
  a clear technical necessity.
- If a requested visual effect would require a workaround instead of a native
  solution, report that explicitly before implementing it.

### 8. Minimize special cases

- Avoid one-off sizing logic for a single form.
- Prefer shared helpers and shared metrics when the same UI pattern is repeated.

### 9. Readability over ornament

- Tree and form styling should improve scanability, hierarchy, and focus.
- Styling should not add noise or reduce available working space.

### 10. Predictable resizing

- Window and panel resizing should preserve readability.
- Switching tabs should not cause distracting width or height jumps unless the
  content genuinely requires it.

## Data contract

The editor should work against stable project data, not hardcoded visual state.

Current priority:

- create/update `screen_layout.json` structures for screens and frames;
- create/update group placement data;
- reflect changes immediately in `GUI Explorer`.

Rules:

- Prefer stable ids over display labels.
- Treat layout data as editable project state.
- Do not couple form rendering logic to gameplay behavior.

## Runtime boundary

`gui_editor.py` may inspect GUI project data, but must not become a second GUI
runtime.

Do not move into the editor:

- Pygame event-loop logic
- runtime animation behavior
- gameplay decisions
- screen orchestration rules from the game itself

## Testing contract

UI contract verification is mandatory.

Any change to `gui_editor.py` that affects layout, sizing, spacing, form
composition, tabs, explorers, or shared widget styling must be covered by
automated checks in:

```text
tests/test_gui_editor.py
```

Do not treat manual inspection as sufficient when a stable UI invariant can be
checked automatically.

When editor behavior changes:

- prefer targeted tests in `tests/test_gui_editor.py`;
- test data creation flows for `Screen`, `Frame`, and `Group`;
- test shared UI invariants for `Screen`, `Frame`, and `Group`;
- test panel sizing policy and absence of fixed panel heights;
- test consistency of shared control metrics;
- test shared `CREATE` composition order;
- test that identity rows are full-width and geometry rows are compact;
- test right-side tab stability when switching views;
- test observable persisted results, not only widget existence;
- keep tests focused on editor contracts, not full application runtime behavior.

## Testable UI Invariants

Translate human UI principles into machine-checkable invariants.

For important UI rules, record three things:

1. principle
2. testable invariant
3. failure meaning

Recommended invariant map for `gui_editor.py`:

### Compactness without readability loss

- Principle:
  compactness must not reduce readability.
- Testable invariant:
  shrinking available height must preserve section natural height and use
  scrolling instead of vertical compression.
- Failure meaning:
  the container is compressing readable content instead of preserving layout.

### Content-first sizing

- Principle:
  section height is determined by content.
- Testable invariant:
  `Screen`, `Frame`, and `Group` panels do not use fixed height and keep a
  content-driven vertical size policy.
- Failure meaning:
  the form is being forced into a preselected height.

### Shared design system

- Principle:
  equal control roles must look and behave equally.
- Testable invariant:
  matching inputs share height metrics; matching buttons share height metrics;
  status labels share the same semantic role.
- Failure meaning:
  one section has diverged from the common form system.

### Form follows data

- Principle:
  identifiers are wide; compact geometry fields stay compact.
- Testable invariant:
  identity inputs are wider than geometry inputs; geometry rows form compact
  two-column grids.
- Failure meaning:
  the layout is no longer reflecting data shape.

### Stable CREATE grammar

- Principle:
  `Screen`, `Frame`, and `Group` share one composition grammar.
- Testable invariant:
  every section preserves the order
  `identity -> geometry -> action -> status`.
- Failure meaning:
  a local layout fix has broken the shared section grammar.

### No overlap

- Principle:
  action and status rows must remain visually separate.
- Testable invariant:
  button geometry and status geometry do not intersect, and the status row stays
  within panel bounds.
- Failure meaning:
  vertical rhythm has collapsed.

### Container-first diagnosis

- Principle:
  container behavior must be validated before local spacing changes.
- Testable invariant:
  `CREATE` lives inside a scrollable container when the left viewport can become
  shorter than the combined natural height of the sections.
- Failure meaning:
  repeated spacing fixes are hiding a wrong container model.

### Predictable resizing

- Principle:
  tab switches must not cause distracting width jumps.
- Testable invariant:
  right-side tabs keep stable width when switching between explorer views.
- Failure meaning:
  tab content is driving uncontrolled container resize.

## UI Work Protocol

Use this protocol for any future UI work in `gui_editor.py`.

### 1. Determine the problem level before editing code

Classify the issue first:

- cosmetic;
- composition-level;
- container/layout behavior;
- architecture-level.

Do not start by tuning paddings or heights until the problem level is known.

### 2. Define the wireframe contract before implementation

If a form, panel, tab, tree, or split view changes structurally:

- define block order first;
- define layout grammar first;
- only then implement widgets and spacing.

### 3. Compactness means efficiency, not compression

- remove irrational empty space before reducing readable spacing;
- optimize width more aggressively than height;
- never compress controls until they visually merge;
- if a layout becomes harder to scan, compactness has failed.

### 4. Readability is the stop condition

Stop and re-evaluate if any refactor causes:

- labels to blend into adjacent controls;
- fields to visually collide;
- action and status rows to crowd each other;
- block boundaries to stop reading clearly.

### 5. Height must not be reduced without a real constraint

If height is not explicitly scarce:

- sections may grow vertically;
- scrolling is acceptable;
- vertical breathing room is allowed;
- do not optimize for minimum height by default.

### 6. Check container behavior before tuning internals

When several sections share one viewport or column, verify first:

- whether the parent compresses child height;
- whether scrolling is required;
- whether child natural size is preserved;
- whether section competition, not local spacing, is the real defect.

### 7. Test root causes, not only symptoms

Prefer tests that validate:

- composition order;
- block separation;
- container behavior;
- non-compression of sections;
- stable structural invariants.

Metric-level tests are secondary.

### 8. Repeated local fixes require escalation

If the same UI problem reappears after one local fix:

- stop treating it as a padding or metric issue;
- state the likely systemic cause explicitly;
- change the layout model if necessary.

### 9. Systemic problems must be reported explicitly

If the real issue is a wrong layout model, wrong container behavior, or wrong
optimization target, state that before the next refactor cycle.

### 10. Required execution order

Follow this order:

```text
contract -> diagnosis -> layout model -> implementation -> tests
```

Do not skip directly from symptoms to parameter tuning.

## Change policy

- Prefer minimal diffs.
- Do not redesign the editor architecture unless explicitly requested.
- Do not add dependencies without explicit approval.
- If a request pushes toward a hack, say so clearly before implementing it.
