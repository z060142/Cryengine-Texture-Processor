# Refactor Phase 51: Model Import Degraded State UI

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 1 item: `P1-4`

## Goal

Make degraded model import states visible in the PySide model import UI without changing the current conversion behavior.

Before this phase, `load_status` and texture `source_mode` were captured, but the imported model list and selected model details could still make fallback filesystem scans look like authoritative Blender/FBX material data.

## What Changed

Updated:

```text
ui_pyside/model_import.py
```

Added UI-facing helper functions:

```text
model_load_state_text()
texture_source_mode_text()
texture_source_summary_text()
```

The imported model row now includes degraded load state suffixes:

```text
asset.fbx [import_only]
asset.fbx [dummy]
asset.fbx [import_only] [diagnostics]
```

The selected model information panel now shows:

```text
Load State
Texture Sources
```

The extracted texture table still stores the raw `source_mode` in each texture record, but displays a readable source label:

```text
filesystem scan (import_only) [filesystem_import_only]
filesystem scan (no bpy) [filesystem_no_bpy]
blender material data [blender]
```

## Preserved Behavior

No export behavior changes.

No RC request JSON fields are added.

No live Qt interaction is required for the new tests; the user-visible formatting is covered through pure helper functions.

## Why This Matters

Phase 1 keeps compatibility fallbacks, but the user must be able to see when material and texture data came from a degraded path.

This phase makes the UI distinction explicit:

```text
loaded -> Blender/FBX material data path
import_only -> model import failed, filesystem texture scan fallback
dummy -> model load failed, no authoritative model data
error -> import exception
```

Phase 2 can later replace these fallback states with stricter CryEngine/RC-derived rules, but the uncertainty is now visible during normal tool use.

## Verification

Passed targeted verification:

```powershell
uv run python -m pytest tests\test_pyside_model_import_diagnostics.py tests\test_model_load_degraded_status.py
uv run python -m compileall ui_pyside\model_import.py tests\test_pyside_model_import_diagnostics.py
```

New tests cover:

```text
model display names include import_only and dummy state
selected-model load state helper explains degraded states
texture source mode labels expose filesystem fallback modes
texture source summary counts source modes
```
