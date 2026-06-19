# Refactor Phase 59: RC Omitted Source Material Diagnostics

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 2 item: request material coverage and face deletion hazards

## Goal

Expose the RC hazard where a source material is omitted from the request `materials` list while other request materials are present.

The converter historically filters out Blender/default placeholder material names such as:

```text
Material
Dots Stroke
```

That is mostly harmless when those placeholders are unused. It is dangerous when the source FBX has polygons assigned to one of those materials and the request `materials` array is otherwise non-empty.

## Source Evidence

RC initializes every source scene material as unused/deletable:

```text
CRYENGINE_Source-release/Code/Tools/RC/ResourceCompilerPC/FBX/FbxConverter.cpp:82-87
```

When request materials are present, a scene material is mapped only if `FindMaterialInfoByName()` finds a matching request material:

```text
CRYENGINE_Source-release/Code/Tools/RC/ResourceCompilerPC/FBX/FbxConverter.cpp:101-105
```

RC falls back to automatic material mapping only when the request `materials` array is empty:

```text
CRYENGINE_Source-release/Code/Tools/RC/ResourceCompilerPC/FBX/FbxConverter.cpp:106-109
```

Faces whose material remap is still negative are deleted:

```text
CRYENGINE_Source-release/Code/Tools/RC/ResourceCompilerPC/FBX/FbxConverter.cpp:214-239
```

So the practical rule is:

```text
If request materials is non-empty, every source material used by polygons needs a matching request material.
```

## What Changed

Updated:

```text
model_processing/material_index_assigner.py
```

Added:

```text
build_omitted_material_diagnostics()
```

It detects ignored source material names that will not appear in request materials after assignment. It only reports this when at least one request material is emitted; if every source material is ignored and the request material list would be empty, RC's automatic fallback still applies.

Updated:

```text
output_formats/material_diagnostics_exporter.py
```

The sidecar report now emits:

```text
rc_omitted_source_material_faces_deleted
```

for omitted default-name source materials when request materials are non-empty.

The diagnostic includes:

```text
material
source_order
polygon_count
used_by_polygons
ignored_material_name
```

Updated tests:

```text
tests/test_material_diagnostics_exporter.py
```

## Current Boundary

This phase reports the hazard. It does not remove the historical default-name filter.

That is deliberate for this phase because some Blender default materials are genuinely unused noise. The safe next repair path is:

```text
if ignored source material has polygon usage -> keep it in request/MTL or ask the user/plugin to remap it explicitly
if ignored source material is unused -> continue suppressing it
```

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_material_diagnostics_exporter.py tests\test_material_index_assigner.py tests\test_rc_request_builder.py tests\test_material_slot_table.py tests\test_rc_smoke_test.py
```

Result:

```text
64 passed
```

New coverage proves:

```text
used ignored source material names are hazardous when other request materials exist
omitted diagnostics include polygon usage evidence
only-ignored source material lists do not warn because RC automatic fallback applies
default RC request JSON remains unchanged
```
