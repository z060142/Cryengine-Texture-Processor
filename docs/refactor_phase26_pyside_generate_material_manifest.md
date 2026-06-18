# Refactor Phase 26: PySide Generate Material Manifest

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Make the Blender FBX material inspector usable from the PySide model import workflow.

Before this phase, users had to run:

```powershell
uv run python -m tools.blender_material_inspector --fbx path\to\asset.fbx
```

Then reopen or reselect the model to see the RC material table sidecar.

## What Changed

The Model Import tab now has a button in the `RC Material Table` section:

```text
Generate Material Table
```

When a selected model is an existing `.fbx`, the button runs:

```python
tools.blender_material_inspector.inspect_fbx_materials("", model_path)
```

Then it reloads:

```text
<asset>.fbx_material_manifest.json
```

and refreshes:

- `Material Table:` summary label
- `RC Material Table` rows

## UI Behavior

- No selected model: button disabled.
- Selected non-FBX model: button disabled or warns that inspection requires FBX.
- Selected FBX model: button enabled.
- Inspector success: UI reloads the sidecar and shows a success message.
- Inspector failure: UI shows the Blender/FBX error in a warning dialog.

## Rule

The normal app workflow can now produce material-table evidence before RC conversion:

```text
Import FBX -> Generate Material Table -> inspect RC material table -> export/request/MTL work
```

This closes one of the gaps between command-line probes and actual user workflow.

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_pyside_model_import_diagnostics.py tests\test_blender_material_inspector.py tests\test_material_manifest.py
uv run python -m compileall ui_pyside tools model_processing tests\test_pyside_model_import_diagnostics.py
```

The tests use a fake inspector to prove that the UI helper runs the inspector, reloads the generated sidecar, and preserves names such as `Stone.001`.

## Remaining Work

- Wire the generated sidecar into actual request JSON / `.mtl` generation for imported models.
- Add UI surfacing for `fixture_material_semantic_alignment` after an RC smoke/import run.
- Consider running the inspector asynchronously for very large FBX files.
