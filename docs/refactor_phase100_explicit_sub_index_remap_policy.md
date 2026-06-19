# Refactor Phase 100: Explicit Sub-Index Remap Policy

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Correct an older diagnostic rule that treated `sub_index != FBX slot` as a
hazard.

Phase 99 proved that this warning is wrong for RC FBX import requests:
`materials[].sub_index` is the authoritative final CE sub-material id, and
RC remaps source face material ids through the request material table.

## Source Evidence

CryEngine source-release files:

```text
Code\Tools\RC\ResourceCompilerPC\FBX\ImportRequest.h
Code\Tools\RC\ResourceCompilerPC\FBX\ImportRequest.cpp
Code\Tools\RC\ResourceCompilerPC\FBX\FbxConverter.cpp
```

Relevant facts:

```text
ImportRequest.cpp maps JSON "sub_index" to SMaterialInfo.finalSubmatIndex.
The field description says it is the submaterial id to store in output asset files.
FbxConverter::PrepareMaterials() maps each scene material name to finalSubmatIndex.
FbxConverter::addMaterial() writes the material into that final sub-material slot.
AppendMesh() remaps per-face material ids through the material remap table.
```

## Sample Evidence

The car sample's embedded `ImportSettings` chunk shows:

```text
request material count: 17
CGF MtlName sub-material count: 16
MTL sub-material count: 17
request sub_index order == MTL sub-material order
request sub_index order prefix == CGF MtlName order
```

Blender's first-seen FBX order differs from the request/MTL/CGF order, but RC
still produced the correct CGF material table because the request carried
explicit `sub_index` values.

## Policy Change

Removed diagnostic:

```text
sub_index_differs_from_fbx_slot_usage_unknown
```

New policy:

```text
Explicit non-negative sub_index values are allowed to differ from the source
FBX material table slot. That is RC's intended remap path.
```

Still hazardous:

```text
duplicate non-negative sub_index values
sub_index >= MAX_SUB_MATERIALS
deleted materials with unknown source polygon usage
case-insensitive material name collisions
```

Historical note:

```text
docs/refactor_phase14_material_slot_diagnostics.md recorded the older hazard.
This phase supersedes that specific rule.
```

## Code Changes

Updated:

```text
model_processing/material_index_assigner.py
tests/test_material_index_assigner.py
tests/test_material_diagnostics_exporter.py
```

The material index assigner no longer warns when a valid assigned `sub_index`
differs from the known FBX slot.

## Verification

Checks run:

```text
uv run python -m pytest tests\test_material_index_assigner.py tests\test_rc_request_builder.py tests\test_material_slot_table.py
uv run python -m pytest tests\test_material_index_assigner.py tests\test_material_diagnostics_exporter.py tests\test_rc_request_builder.py tests\test_material_slot_table.py
uv run python -m pytest tests
uv run python -m compileall model_processing output_formats tests
uv lock --check
git diff --check
```

Result:

```text
initial request/slot tests: 49 passed
targeted diagnostics/request/slot tests: 78 passed
full test suite: 316 passed
compileall: passed
uv lock --check: passed
git diff --check: passed
```
