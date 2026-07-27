# Refactor Phase 50: Core Manager Contracts

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 1 item: `P1-3`

## Goal

Bound the remaining placeholder-style core manager modules without redesigning the application architecture.

The scoped modules were:

```text
core/texture_manager.py
core/model_manager.py
core/material_manager.py
```

## Current Caller Findings

`TextureManager` is active and used by the Tk/PySide texture import UI and batch processing path for classification, de-duplication, grouping, and UI-facing group state.

`ModelManager` is not used by the current PySide model import/export flow. The active model path is:

```text
model_processing.model_loader
model_processing.texture_extractor
model_processing.model_export_context
model_processing.fbx_exporter
```

`MaterialManager` is not the active `.mtl` generation path. The active material file path is:

```text
model_processing.material_texture_resolver
model_processing.material_slot_table
output_formats.mtl_exporter
output_formats.material_diagnostics_exporter
```

## What Changed

### TextureManager

`TextureGroup.generate_intermediate_formats()` and `TextureGroup.generate_output_formats()` are now explicit state accessors for compatibility. They no longer claim to be hidden processing implementations.

Actual image processing remains owned by:

```text
core.batch_processor.BatchProcessor
intermediate_formats/*
output_formats/*
```

`TextureManager.update_texture_type()` now handles moving an existing texture from one known slot to another, not only from the `unknown` list.

### ModelManager

`ModelManager` is now documented and marked as a legacy compatibility facade.

It preserves its old minimal return shape but now records:

```text
manager_status = legacy_compatibility_facade
load_status = legacy_stub
```

This prevents the class from looking like the current model conversion backend.

### MaterialManager

`MaterialManager` is now documented as a small in-memory material registry, not the active CryEngine `.mtl` generator.

`apply_to_model()` now performs its narrow compatibility behavior for dict models:

```text
model material names
  -> matching TextureGroup by name/base_name
  -> Material registry texture slots
```

`ddna` output is now recorded in the material's `normal` texture slot.

## Preserved Behavior

No active PySide export path was redirected.

No RC request JSON or `.mtl` XML behavior changed.

Legacy class names and method names remain available.

## Verification

Passed targeted verification:

```powershell
uv run python -m pytest tests\test_core_managers.py
uv run python -m compileall core\texture_manager.py core\model_manager.py core\material_manager.py tests\test_core_managers.py
```

New tests cover:

```text
TextureManager de-duplication and grouping
TextureManager reclassification between known slots
TextureGroup state-accessor methods
ModelManager legacy status contract
MaterialManager narrow dict-model application behavior
```
