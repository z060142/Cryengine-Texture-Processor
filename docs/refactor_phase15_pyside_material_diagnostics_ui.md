# Refactor Phase 15: PySide Material Diagnostics UI

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Surface the material-slot diagnostics from phase 14 in the PySide model import UI.

The converter should not require a developer to inspect smoke reports to see obvious material-slot hazards. Imported models now show diagnostics directly in the model tab.

## What Changed

- `ui_pyside.model_import.collect_model_material_diagnostics()` collects diagnostics from the shared material assignment logic.
- Imported model records now store `material_diagnostics`.
- The imported model list appends:
  - `[hazard]` when any diagnostic has severity `hazard`
  - `[diagnostics]` when non-hazard diagnostics exist
- The selected model info panel now shows a diagnostics count.
- The model import tab now includes a compact `Material Slot Diagnostics` table with:
  - severity
  - material
  - FBX slot -> assigned sub-index
  - message

## Why This Matters

Phase 13 proved that deleted request materials do not remove geometry material ids that are still used by the FBX. Phase 14 converted that rule into preflight diagnostics. This phase makes the diagnostic visible during normal tool use.

Example hazard shown in the UI:

```text
Removed
FBX 1 -> sub -1
Deleted material has a known FBX slot...
```

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_pyside_model_import_diagnostics.py tests\test_material_index_assigner.py
```

Offscreen PySide smoke:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
uv run python - <<'PY'
import sys
from PySide6.QtWidgets import QApplication
from ui_pyside.model_import import ModelImportPanel, collect_model_material_diagnostics

app = QApplication.instance() or QApplication(sys.argv)
panel = ModelImportPanel()
diags = collect_model_material_diagnostics({
    'materials': [
        {'name': 'Visible', 'id': 1},
        {'name': 'Removed', 'id': 2, 'deleted': True},
    ]
})
panel.imported_models_info = [{
    'filename': 'probe.fbx',
    'path': 'probe.fbx',
    'materials': 2,
    'extracted_textures': [],
    'material_diagnostics': diags,
}]
panel._update_model_list_display()
assert panel.models_list.item(0).text() == 'probe.fbx [hazard]'
assert panel.diagnostics_table.rowCount() == 1
assert panel.diagnostics_table.item(0, 1).text() == 'Removed'
PY
```

## Remaining Work

- Done in phase 16: persist diagnostics next to normal export artifacts as `<model>.material_diagnostics.json`.
- Add true polygon material-slot usage extraction so hazards can become precise per-slot validation instead of usage-unknown warnings.
- Add UI actions for resolving a hazard, such as converting deleted used slots back into explicit placeholder materials.
