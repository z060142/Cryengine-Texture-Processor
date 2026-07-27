# Refactor Phase 57: RC Case-Insensitive Material Names

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 2 item: material id and request material-name matching

## Goal

Make RC's case-insensitive request material lookup visible in converter diagnostics.

This closes another material-id trap: an FBX or Blender scene can expose two material names that differ only by case, but RC cannot target them independently through the request `materials` array.

## Source Evidence

Request material entries carry the source scene material name:

```text
CRYENGINE_Source-release/Code/Tools/RC/ResourceCompilerPC/FBX/ImportRequest.cpp:47-85
```

RC looks up a request material for each scene material here:

```text
CRYENGINE_Source-release/Code/Tools/RC/ResourceCompilerPC/FBX/FbxConverter.cpp:101-104
```

The lookup implementation is:

```text
CRYENGINE_Source-release/Code/Tools/RC/ResourceCompilerPC/FBX/ImportRequest.cpp:291-301
```

Important detail:

```text
StringHelpers::EqualsIgnoreCase(name, materials[i].sourceName)
```

RC scans request materials from first to last and returns the first case-insensitive name match.

## Practical Rule

These request materials are not independently addressable by RC:

```json
[
  {"name": "Wood", "sub_index": 0},
  {"name": "wood", "sub_index": 1}
]
```

If the source scene material is `Wood` or `wood`, `FindMaterialInfoByName()` can match the first entry before the second one ever has a chance.

The exact effect depends on the source material order and request order, but the safe converter rule is:

```text
Names that differ only by case are an RC material-name collision.
```

## What Changed

Updated:

```text
model_processing/material_index_assigner.py
```

The normalized material records now detect case-insensitive clean-name collisions. The converter keeps both records to preserve current behavior, but each record receives a hazard diagnostic:

```text
rc_case_insensitive_material_name_collision
```

The diagnostic includes:

```text
conflicting_material_names
fbx_slot
sub_index
```

Updated:

```text
output_formats/material_diagnostics_exporter.py
```

Material sidecars now expose:

```text
case_insensitive_name_conflict
case_insensitive_material_names
```

and copy that evidence onto diagnostics.

Updated tests:

```text
tests/test_material_index_assigner.py
tests/test_material_diagnostics_exporter.py
tests/test_rc_request_builder.py
```

## Current Boundary

This phase reports the hazard. It does not rename, merge, or delete either material.

That is intentional for now: automatically renaming a source material would only be correct if the FBX scene is also rewritten to use that new name. Automatically deleting one material could remove geometry. The next safe repair path should be explicit UI/plugin workflow:

```text
detect collision -> ask user/plugin to rename source material -> regenerate FBX/material manifest/request/MTL together
```

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_material_index_assigner.py tests\test_material_diagnostics_exporter.py tests\test_rc_request_builder.py tests\test_material_slot_table.py tests\test_rc_smoke_test.py
```

Result:

```text
58 passed
```

New coverage proves:

```text
Wood and wood remain distinct converter records for now
both records receive rc_case_insensitive_material_name_collision
sidecar reports expose case-insensitive conflict fields
request material diagnostics can include the collision when requested
default RC request JSON remains free of diagnostics
```
