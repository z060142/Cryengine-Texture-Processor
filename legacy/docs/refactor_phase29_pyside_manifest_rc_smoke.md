# Refactor Phase 29: PySide Manifest RC Smoke

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Expose the manifest-driven RC smoke proof path inside the PySide Model Import tab.

Before this phase, the command line could prove:

```text
FBX -> .fbx_material_manifest.json -> request JSON / .mtl -> RC -> material_report
```

but the UI stopped at generating and displaying the material table.

## What Changed

The Model Import tab now has a second button in the `RC Material Table` section:

```text
Run RC Material Smoke
```

For a selected FBX, it:

1. Reloads the material manifest sidecar.
2. Uses `tools.rc_smoke_test.material_specs_from_manifest`.
3. Runs `tools.rc_smoke_test.run_rc_smoke_test`.
4. Writes the smoke bundle under:

```text
<fbx folder>/<fbx stem>_rc_smoke_work
```

5. Reads `<asset>.material_report.json`.
6. Shows the RC material smoke status in the selected-model information panel.

The UI helper records:

```json
{
  "success": true,
  "work_dir": ".../asset_rc_smoke_work",
  "material_report_path": ".../asset.material_report.json",
  "semantic_alignment_ok": true,
  "cgf_material_id_alignment_ok": true
}
```

## Rule

The UI RC smoke path must not build a second material table.

It always derives request/MTL material specs from the selected FBX sidecar:

```text
.fixture_manifest.json or .fbx_material_manifest.json
```

That keeps this chain single-source:

```text
Blender/fixture material table -> request materials[].sub_index -> .mtl slot order -> RC report alignment
```

## UI Behavior

- No selected model: smoke button disabled.
- Selected existing FBX: smoke button enabled.
- Missing material sidecar: warning asks the user to generate/provide the material table first.
- Missing or invalid `rc_exe_path`: smoke result shows the runner error.
- Successful run: status shows `passed`, plus semantic and CGF-id checks when the report provides them.
- Failed run: status shows `failed` and the runner/report error.

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_pyside_model_import_diagnostics.py tests\test_rc_smoke_test.py
uv run python -m pytest tests
uv run python -m compileall main.py model_processing output_formats utils tools tests ui_pyside
uv lock
git diff --check
```

The tests use a fake smoke runner to prove that the PySide helper:

- reads manifest material names such as `Stone` and `Stone.001`
- preserves manifest `sub_index` values
- derives the default smoke work directory from the FBX stem
- reads semantic and CGF material-id alignment from the generated report

## Remaining Work

- Run the PySide action manually against the controlled duplicate-name FBX with real `rc.exe`.
- Add richer report viewing instead of only the status summary.
- Carry the same material manifest table into the upcoming material-ball / `.mtl` schema work.
