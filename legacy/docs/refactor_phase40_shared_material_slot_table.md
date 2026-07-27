# Refactor Phase 40: Shared RC Material Slot Table

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Keep existing exporter behavior while moving RC-visible material slot assignment into one shared table builder.

Before this phase, the same assignment chain was repeated across:

```text
output_formats/rc_request_builder.py
output_formats/mtl_exporter.py
output_formats/material_diagnostics_exporter.py
tools/rc_smoke_test.py
```

That made the current behavior harder to preserve and made future CE/RC-spec changes risky.

## What Changed

Added:

```text
model_processing/material_slot_table.py
```

Main helpers:

```text
build_material_slot_records()
build_expanded_material_slot_table()
material_slot_from_record()
```

The shared flow is now:

```text
source materials
  -> material_manifest_materials()
  -> assign_material_sub_indices()
  -> RC request / MTL / diagnostics / smoke preflight consumers
```

Consumers updated:

```text
output_formats/rc_request_builder.py
output_formats/mtl_exporter.py
output_formats/material_diagnostics_exporter.py
tools/rc_smoke_test.py
```

## Preserved Behavior

The refactor preserves the existing external behavior:

```text
empty MTL material input -> Default sub-material
known FBX material id -> preferred zero-based sub_index
manifest material table -> pinned order and explicit sub_index
deleted material -> request-side sub_index -1, omitted from expanded MTL slots
slot gaps -> unassigned placeholder sub-materials
diagnostics -> still attached to hazardous records
```

## Why This Matters

The next material/RC phase needs one place to encode the real rules.

This phase does not claim new CryEngine behavior. It reduces duplicated assignment code so future source-derived or RC-probed rules can be swapped into the slot table without silently desynchronizing request JSON, `.mtl`, diagnostics, and smoke reports.

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_material_slot_table.py tests\test_material_manifest.py tests\test_material_index_assigner.py tests\test_material_diagnostics_exporter.py tests\test_rc_smoke_test.py tests\test_rc_request_builder.py tests\test_mtl_exporter.py
```

New tests cover:

```text
manifest resolution before assignment
expanded slot gap placeholders
metadata preservation
deleted-material omission from MTL slots
default material behavior
optional placeholder dropping
```
