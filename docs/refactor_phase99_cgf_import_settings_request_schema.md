# Refactor Phase 99: CGF ImportSettings Request Schema

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Extract the original RC FBX import request JSON from the car sample's output
CGF and tie it to the final CGF/MTL material slot order.

Phase 98 proved that CGF `MeshSubsets.material_id` indexes the CGF `MtlName`
sub-material table, and that this table matches the MTL sub-material order
prefix. Phase 99 closes the missing link by reading the `ImportSettings` chunk
embedded in the CGF.

## Evidence Artifacts

Generated from:

```text
S:\Crytek\crytek\Stripped to the bone\example\car\kb3d_citycarsessentialssedan-native.cgf
```

Artifacts:

```text
docs/phase99_car_example_cgf_import_settings_probe.json
docs/phase99_car_example_import_settings_raw.json
docs/phase99_car_example_import_settings_summary.json
docs/refactor_phase99_cgf_import_settings_request_schema.md
```

## Source-Release Evidence

`ChunkType_ImportSettings` is documented by implementation, not user-facing
docs:

```text
Code\Tools\RC\ResourceCompilerPC\FBX\ImportRequest.h
Code\Tools\RC\ResourceCompilerPC\FBX\ImportRequest.cpp
Code\Tools\RC\ResourceCompilerPC\FBX\FbxConverter.cpp
```

Important source facts:

```text
ImportRequest.h:
SMaterialInfo.finalSubmatIndex is the request material's final sub-material id.
Values below zero mean faces using that material are deleted.

ImportRequest.cpp:
JSON key "name" maps to SMaterialInfo.sourceName.
JSON key "physicalize" maps to the CE physicalization enum.
JSON key "sub_index" maps to finalSubmatIndex.
The "sub_index" field is described as the submaterial id to store in output asset files.
sub_index >= MAX_SUB_MATERIALS is converted to -1.

FbxConverter.cpp:
PrepareMaterials() looks up each scene material by name in the import request.
addMaterial(finalSubmatIndex, sourceName, physicalization) writes that name into the final CGF material table at sub_index.
Missing intermediate slots are filled with "-unused-".
Mesh face material ids are remapped through this final material table.
```

## ImportSettings Chunk

The car CGF contains:

```text
ChunkType_ImportSettings
chunk id: 173
version: 0
size: 10828 bytes
```

The chunk decodes as UTF-8 JSON.

Top-level keys observed:

```text
animation
autolodsettings
editorMaterialMeta
editorNodeMeta
forward_up_axes
globalSettings
ignore_custom_normals
ignore_uv
material_filename
materials
merge_all_nodes
nodes
output_ext
scale
scene_origin
source_filename
unit_size
use_32_bit_positions
version
```

Core values:

```text
version: 1
source_filename: kb3d_citycarsessentialssedan-native.fbx
output_ext: cgf
material_filename: kb3d_citycarsessentialssedan-native
unit_size: file
scale: 1.0
forward_up_axes: +Z+Y
merge_all_nodes: false
scene_origin: false
ignore_custom_normals: false
ignore_uv: false
use_32_bit_positions: false
```

## Material Request Schema

Each material entry in this sample has:

```json
{
  "name": "KB3D_CEV_UndercarriageTrim",
  "file": "",
  "physicalize": "no",
  "sub_index": 0,
  "ui_autoflag": true
}
```

Fields with source-backed meaning:

```text
name:
  Source scene material name used by FindMaterialInfoByName().

physicalize:
  Physicalization policy. Observed string values in source:
  no, default, obstruct, no_collide, proxy_only.

sub_index:
  Final CE sub-material id written into output asset files.
  This value controls the final CGF/MTL material slot.
```

Fields observed but not yet source-mapped:

```text
file:
  Empty for this sample. Needs more evidence before assigning behavior.

ui_autoflag:
  Present in this editor-authored sample. Not read by the RC ImportRequest
  serializer code inspected in this phase, so treat as editor metadata.
```

## Slot Alignment

Counts:

```text
request material count: 17
CGF MtlName sub-material count: 16
MTL sub-material count: 17
CGF used material ids: 0..15
```

Observed alignments:

```text
request material order == MTL sub-material order: true
request sub_index order == MTL sub-material order: true
request sub_index order prefix == CGF MtlName order: true
CGF MtlName order == MTL order prefix: true
CGF MtlName order == Blender first-seen FBX material order: false
```

The material request includes:

```json
{
  "name": "<unassigned>",
  "file": "",
  "physicalize": "no",
  "sub_index": 16,
  "ui_autoflag": true
}
```

The MTL contains this same slot as slot 16. The CGF `MtlName` table does not:

```text
request/MTL slot 16: <unassigned>
CGF MtlName slots: 0..15 only
CGF MeshSubsets.material_id: 0..15 only
```

## Rule Implications

Evidence-supported rules:

```text
For FBX import requests, materials[].sub_index is the authoritative final CE sub-material slot.
CGF MeshSubsets.material_id uses this final sub-material table after RC remapping.
The CGF MtlName table stores the material names used by those final ids.
The MTL sub-material order follows request sub_index order.
The MTL may keep an extra <unassigned> slot that is not present in the CGF material table.
Blender's first-seen FBX material order is not authoritative for CE sub_index.
```

Converter implication:

```text
A custom converter or Blender plugin must generate request.materials with stable,
explicit sub_index values. The safest source for these values is the intended
CE material-slot table, not Blender's global material discovery order.
```

## Verification

Checks run:

```text
uv run python -m pytest tests\test_cgf_material_probe.py
uv run python -m pytest tests\test_cgf_material_probe.py tests\test_cgf_material_reader.py tests\test_material_mapping_report.py tests\test_rc_smoke_test.py
uv run python -m pytest tests
uv run python -m compileall utils tools tests
uv lock --check
git diff --check
```

Results:

```text
CGF ImportSettings test: 3 passed
targeted CGF/material/RC tests: 59 passed
full test suite: 316 passed
compileall: passed
uv lock --check: passed
git diff --check: passed
```
