# Resource Picker Refactor Backlog

Source: `tools/resource_picker_refactor_tz.md`

Goal: rebuild `tools/resource_picker.py` around the new source-of-truth model:
`Group` files define resource usage through `GRAPHICS`, PNG metadata defines frame slicing,
and `resource_manifest.json` is only a derived index for `ResourceManager`.

## Principles

- `GRAPHICS` in `groups_store/*_group.py` is the source of truth for manifest contents.
- PNG metadata is the source of truth for `frame_width` and `frame_height`.
- `resource_manifest.json` is generated/updated from `GRAPHICS` and PNG metadata.
- The UI must not manually edit manifest records.
- The picker copies tuples for manual insertion into `GRAPHICS`; it does not edit group files.

## P0. Stabilize Current Tool Boundaries

Files:

- `tools/resource_picker.py`
- `core/resource.py`

Tasks:

- Document the current behavior of `Generate manifest`, `Save manifest`, `Prune manifest`, `Save record`, and `Save + Copy GRAPHICS`.
- Mark which current actions will be removed, renamed, or replaced.
- Keep the current raw PNG preview and tuple-copy behavior working while refactoring.
- Add a small smoke path that can instantiate the app services without opening Tk widgets where possible.

Done when:

- There is a clear mapping from current UI commands to future commands.
- Existing tuple copy from raw PNG still works.
- `py_compile` passes for `tools/resource_picker.py` and `core/resource.py`.

## P1. Split Data Model From Tkinter UI

Files:

- `tools/resource_picker.py`
- optional new module: `tools/resource_picker_models.py`
- optional new module: `tools/resource_picker_services.py`

Tasks:

- Extract plain data models for PNG assets, group graphics entries, manifest entries, and operation reports.
- Extract scanning of `assets/` PNG files from widget code.
- Extract scanning of `groups_store/*_group.py` and reading `GRAPHICS`.
- Extract tuple/snippet generation.
- Keep Tkinter code responsible only for rendering and event wiring.

Done when:

- PNG scanning can be called without creating `tk.Tk()`.
- `GRAPHICS` scanning can be called without creating `tk.Tk()`.
- Snippet generation has focused tests or a minimal smoke check.

## P2. Add PNG Metadata Read/Write Support

Files:

- `core/resource.py`
- `tools/resource_picker.py`
- optional new module: `tools/resource_picker_png_metadata.py`

Tasks:

- Define exact PNG metadata keys for frame slicing, for example `frame_width` and `frame_height`.
- Add helper to read frame metadata from a PNG.
- Add helper to write frame metadata into a PNG.
- Validate metadata: positive integers, frame size not larger than image size, currently one-column sprite sheet rule if that rule remains.
- Report missing or invalid metadata without silently treating manifest values as truth.

Done when:

- A selected PNG can show current metadata.
- `Save PNG metadata` writes `frame_width` and `frame_height` into the PNG.
- Missing or invalid metadata is shown in Output / Warnings.
- Manifest is not edited by saving PNG metadata.

## P3. Replace Raw Assets Tab With PNG Explorer

Files:

- `tools/resource_picker.py`

Tasks:

- Rename/reframe `Raw assets` as `PNG Explorer`.
- Show recursive PNG tree from `assets/`.
- Search only by PNG resource name in this tab.
- On selection, show preview and PNG metadata.
- Replace `Copy GRAPHICS snippet` with `Get PNG resource`.
- Generate tuple:

```python
("local_layer_name", "resource.key")
```

Done when:

- User can select any PNG in `assets/`.
- Preview updates for selected PNG.
- `Get PNG resource` copies the tuple and shows it in Output / Warnings.
- Search filters by PNG name, not by manifest JSON or status text.

## P4. Replace Manifest Editing Form With PNG Metadata Editor

Files:

- `tools/resource_picker.py`

Tasks:

- Remove manual manifest record fields as an editing concept.
- Keep or rename the fields to metadata-only fields: `frame_width`, `frame_height`.
- Remove or disable `resource_key` and `path` editing as manifest record edits.
- Replace `Save record` with `Save PNG metadata`.
- Remove `Save + Copy GRAPHICS` or split it into explicit `Save PNG metadata` and `Get PNG resource`.

Done when:

- User cannot manually edit manifest `resource_key` or `path` through the form.
- User can edit only PNG frame metadata.
- Saving metadata does not directly rebuild manifest unless a separate manifest command is used.

## P5. Build Manifest From Group GRAPHICS

Files:

- `tools/resource_picker.py`
- `core/resource.py`
- optional new module: `tools/resource_picker_manifest_builder.py`

Tasks:

- Implement `Build Manifest`.
- Find all group modules in `groups_store`.
- Read `GRAPHICS` entries from each group module.
- Resolve each `resource_key` to a PNG path under `assets/`.
- Read `frame_width` and `frame_height` from PNG metadata.
- Generate `resource_manifest.json` from this derived data.
- Produce a report with added resources, missing PNG files, and invalid/missing metadata.

Done when:

- A new manifest can be generated from `GRAPHICS` plus PNG metadata.
- The command does not include unused PNG files that are not referenced by `GRAPHICS`.
- Missing PNG and invalid metadata are reported clearly.

## P6. Add Manifest Update

Files:

- `tools/resource_picker.py`
- `core/resource.py`

Tasks:

- Implement `Manifest Update`.
- Compare current manifest contents with current `GRAPHICS` usage.
- Add resources newly referenced by `GRAPHICS`.
- Remove resources no longer referenced by `GRAPHICS`.
- Refresh frame sizes from PNG metadata.
- Preserve only data that is still part of the derived manifest model.
- Produce a report with added, removed, changed, missing, and invalid resources.

Done when:

- Manifest composition matches current `GRAPHICS`.
- Frame sizes in manifest match PNG metadata.
- No manual manifest record editing is required.

## P7. Add Manifest Explorer

Files:

- `tools/resource_picker.py`

Tasks:

- Replace the current flat/path manifest tree with a `Group -> PNG resources` tree.
- Root nodes are group files or group IDs.
- Child nodes are `GRAPHICS` tuples with local layer name and `resource_key`.
- Show status for each child: OK, missing manifest entry, missing PNG, missing metadata, invalid metadata.
- Selecting a resource shows the associated PNG preview and metadata.

Done when:

- The manifest view reflects group resource usage, not the folder structure of `assets/`.
- Search in this tab filters the `Group -> PNG resources` tree by PNG resource name.
- Selecting a manifest resource updates preview and metadata panel.

## P8. Improve Preview For Sprite Sheets

Files:

- `tools/resource_picker.py`

Tasks:

- Treat every selected PNG as a sprite sheet, even if it has one frame.
- Use PNG metadata to determine frame dimensions.
- Optionally draw a frame grid overlay in preview.
- Show PNG size, frame size, rows, and frame count.
- Warn when metadata does not match supported slicing rules.

Done when:

- Preview remains useful for both single-frame PNGs and sprite sheets.
- User can visually understand the configured frame slicing.

## P9. Rework Output / Warnings

Files:

- `tools/resource_picker.py`

Tasks:

- Use one consistent Output / Warnings panel for snippets, build reports, update reports, and validation warnings.
- Avoid relying only on modal dialogs for non-fatal warnings.
- Keep copied tuple visible after copy.
- Make reports readable enough to paste into a debugging note.

Done when:

- `Get PNG resource`, `Build Manifest`, and `Manifest Update` all write useful output.
- Missing files and invalid metadata are visible without opening a traceback.

## P10. Remove Legacy Manifest Editing Commands

Files:

- `tools/resource_picker.py`
- docs/backlog references if needed

Tasks:

- Remove `Save record`.
- Remove `Save + Copy GRAPHICS`.
- Remove direct editing of manifest `resource_key`, `path`, `frame_width`, and `frame_height`.
- Rename or remove `Generate manifest`, `Save manifest`, and `Prune manifest` if their semantics conflict with the new model.
- Keep only commands that match the new source-of-truth model.

Done when:

- UI no longer suggests that manifest records are user-authored.
- All manifest writes happen through `Build Manifest` or `Manifest Update`.

## P11. Verification

Files:

- `tools/resource_picker.py`
- `core/resource.py`
- optional test files if a test folder is introduced

Tasks:

- Run `py_compile` on touched modules.
- Add or run smoke checks for:
  - PNG asset scan;
  - group `GRAPHICS` scan;
  - tuple generation;
  - manifest build from `GRAPHICS`;
  - manifest update report generation.
- Manually launch Resource Picker and verify basic UI wiring.

Done when:

- `py_compile` passes.
- Smoke checks pass.
- The app opens and the main workflows are reachable.

## Suggested Implementation Order

1. P1: split non-UI services from Tkinter.
2. P2: add PNG metadata read/write.
3. P3: convert Raw assets to PNG Explorer.
4. P4: convert manifest edit form to PNG Metadata Editor.
5. P5: implement Build Manifest.
6. P6: implement Manifest Update.
7. P7: implement Manifest Explorer.
8. P8-P9: improve preview and reporting.
9. P10-P11: remove legacy commands and verify.

## Open Questions

- Exact PNG metadata key names: use `frame_width` / `frame_height`, or namespaced keys?
- Should `Build Manifest` fail on missing metadata, or generate entries with warnings and default full-image frame size?
- Should `Manifest Update` remove unused manifest resources automatically, or ask for confirmation?
- Should group scanning import modules, parse AST, or support both? Importing is simple but can execute module-level code.
- Should the tool keep the current `resource_manifest.json` backup before overwriting it?
