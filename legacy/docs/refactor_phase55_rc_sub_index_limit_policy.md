# Refactor Phase 55: RC Sub-Index Limit Policy

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 2 item: material id and request material mapping

## Goal

Make the converter apply RC's `sub_index` limit before writing request JSON, MTL slot tables, or diagnostics.

Phase 54 recorded the source-backed rule. This phase wires that rule into the material assignment path so the tool no longer presents out-of-range material ids as valid CryEngine slots.

## Source Evidence

RC request material parsing:

```text
CRYENGINE_Source-release/Code/Tools/RC/ResourceCompilerPC/FBX/ImportRequest.cpp:81-85
```

RC reads `sub_index` into `finalSubmatIndex`. If the value is greater than or equal to `MAX_SUB_MATERIALS`, it sets it to `-1`.

The limit is:

```text
CRYENGINE_Source-release/Code/CryEngine/CryCommon/Cry3DEngine/CGF/CryHeaders.h:10-11
MAX_SUB_MATERIALS = 128
```

RC material table construction:

```text
CRYENGINE_Source-release/Code/Tools/RC/ResourceCompilerPC/FBX/FbxConverter.cpp:101-109
CRYENGINE_Source-release/Code/Tools/RC/ResourceCompilerPC/FBX/FbxConverter.cpp:167-172
```

`FbxConverter` maps a source scene material by name through `FindMaterialInfoByName`. `addMaterial()` returns `-1` for any `submatIndex < 0` or `submatIndex >= MAX_SUB_MATERIALS`.

The practical meaning is:

```text
sub_index 0..127: supported final sub-material id
sub_index -1: delete / do not add this material to the final CGF material table
sub_index >= 128: normalized by RC to -1, then treated as delete
```

## What Changed

Added:

```text
model_processing/rc_material_policy.py
```

This module owns the shared source-backed material-slot limit:

```text
RC_MAX_SUB_MATERIALS = 128
normalize_rc_sub_index()
is_supported_rc_sub_index()
```

Updated:

```text
model_processing/material_index_assigner.py
```

All assignment sources now pass through the RC normalization rule:

```text
explicit sub_index
FBX material id derived slot
existing .mtl child order fallback
first-free fallback
```

When a value is out of range, the record keeps:

```text
sub_index = -1
requested_sub_index = original value
reason = <assignment_reason>_out_of_range
```

and emits a hazard diagnostic:

```text
rc_sub_index_out_of_range_deleted
```

Updated:

```text
model_processing/material_slot_table.py
output_formats/material_diagnostics_exporter.py
output_formats/rc_import_schema.py
```

The expanded MTL slot table now omits out-of-range materials instead of allocating hundreds of slots that RC cannot use. Diagnostics and request material payloads now expose the same deletion hazard that RC would apply.

## Why This Matters

Before this phase, the converter could accept or generate a request material like:

```json
{"name": "TooHigh", "physicalize": "no_collide", "sub_index": 128}
```

RC does not keep that as slot 128. It turns it into:

```json
{"name": "TooHigh", "sub_index": -1}
```

That can delete geometry using the source material. The UI, sidecars, MTL exporter, and future Blender plugin must not describe such a material as a valid slot.

## Current Boundary

The converter now mirrors RC's single-material-table limit for one request/MTL output:

```text
valid sub-material ids are 0 through 127
128 or above is a deletion hazard
```

This phase does not implement Sandbox Mesh Importer's multi-uber-material partitioning for source assets with more than 128 materials.

Source hint for that future work:

```text
CRYENGINE_Source-release/Code/Sandbox/Plugins/MeshImporter/MainDialog.cpp:1065-1066
CRYENGINE_Source-release/Code/Sandbox/Plugins/MeshImporter/MainDialog.cpp:2105-2118
```

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_material_index_assigner.py tests\test_material_slot_table.py tests\test_rc_request_builder.py tests\test_material_diagnostics_exporter.py tests\test_mtl_exporter.py tests\test_rc_smoke_test.py
```

Result:

```text
63 passed
```

New coverage proves:

```text
explicit sub_index 128 becomes -1 with rc_sub_index_out_of_range_deleted
FBX material id 129 maps to requested slot 128, then becomes -1
request material JSON emits the normalized value and diagnostic when requested
expanded MTL slot tables omit out-of-range slots
diagnostic sidecars preserve requested_sub_index for investigation
```
