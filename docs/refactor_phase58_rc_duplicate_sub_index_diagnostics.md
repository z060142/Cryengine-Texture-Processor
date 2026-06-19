# Refactor Phase 58: RC Duplicate Sub-Index Diagnostics

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 2 item: material id and request sub-material mapping

## Goal

Expose the RC hazard where two request materials map to the same non-negative `sub_index`.

This matters because `sub_index` is the final CGF sub-material id. If two source materials share one final id, geometry can still remap through that shared id while the final CGF material slot name and physicalization are overwritten by whichever material RC processes last for that slot.

## Source Evidence

RC maps scene materials to request materials here:

```text
CRYENGINE_Source-release/Code/Tools/RC/ResourceCompilerPC/FBX/FbxConverter.cpp:90-104
```

The loop walks source scene materials in reverse order:

```text
for (int i = pScene->GetMaterialCount() - 1; i >= 0; --i)
```

For each matched request material, RC calls:

```text
addMaterial(pMatInfo->finalSubmatIndex, pMatInfo->sourceName, pMatInfo->physicalization)
```

The final material slot is written here:

```text
CRYENGINE_Source-release/Code/Tools/RC/ResourceCompilerPC/FBX/FbxConverter.cpp:167-193
```

Important lines:

```text
190: cry_strcpy(m_pCgfMaterial->subMaterials[submatIndex]->name, name);
191: m_pCgfMaterial->subMaterials[submatIndex]->nPhysicalizeType = physicalization;
```

There is no duplicate-slot guard. A later write to the same `submatIndex` replaces the slot's visible name and physicalization.

## Practical Rule

This is hazardous:

```json
[
  {"name": "Wood", "sub_index": 0, "physicalize": "no_collide"},
  {"name": "Metal", "sub_index": 0, "physicalize": "default"}
]
```

Both source materials can remap geometry through final material id `0`, but the final CGF sub-material slot can only hold one name and one physicalize type.

The exact winner depends on source material order and RC's reverse traversal, so the safe converter rule is:

```text
Only one non-negative request material should target a given sub_index.
```

## What Changed

Updated:

```text
model_processing/material_index_assigner.py
```

After assigning sub-indices, records are grouped by non-negative `sub_index`. Any group with more than one material gets:

```text
duplicate_sub_index_conflict = true
duplicate_sub_index_material_names = [...]
```

and each record receives a hazard diagnostic:

```text
rc_duplicate_sub_index_overwrites_material
```

Updated:

```text
output_formats/material_diagnostics_exporter.py
```

Material sidecars now expose:

```text
duplicate_sub_index_conflict
duplicate_sub_index_material_names
```

and copy those fields onto diagnostics.

Updated tests:

```text
tests/test_material_index_assigner.py
tests/test_material_diagnostics_exporter.py
tests/test_rc_request_builder.py
```

## Current Boundary

This phase reports duplicate `sub_index` hazards. It does not automatically reassign explicit duplicate slots.

That is deliberate. If the user or a manifest explicitly pins both materials to the same slot, silently changing one slot can desynchronize:

```text
FBX scene material order
request materials
.mtl child order
expected CGF material ids
```

The safe repair path should be an explicit UI/plugin operation that updates the source material table and regenerated outputs together.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_material_index_assigner.py tests\test_material_diagnostics_exporter.py tests\test_rc_request_builder.py tests\test_material_slot_table.py tests\test_mtl_exporter.py tests\test_rc_smoke_test.py
```

Result:

```text
73 passed
```

New coverage proves:

```text
explicit duplicate sub_index values are preserved for compatibility
both duplicate records receive rc_duplicate_sub_index_overwrites_material
sidecar reports expose duplicate_sub_index_conflict fields
request material diagnostics can include duplicate-slot hazards when requested
default RC request JSON remains free of diagnostics
```
