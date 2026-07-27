# Refactor Phase 54: Source-Backed RC Import Request Schema

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 2 item: RC FBX request JSON schema

## Goal

Turn the RC FBX import request JSON schema from CryEngine source into a converter-side contract.

This phase directly addresses the question of what JSON fields tell `rc.exe` how to convert an FBX into CryEngine model assets.

## Source Evidence

Request wrapper:

```text
CRYENGINE_Source-release/Code/Tools/RC/ResourceCompilerPC/FBX/ImportRequest.cpp:275-284
```

RC opens JSON with:

```text
ar(*this, "request", "Import request")
```

So the root JSON object must contain:

```json
{
  "request": {}
}
```

Root request fields:

```text
CRYENGINE_Source-release/Code/Tools/RC/ResourceCompilerPC/FBX/ImportRequest.cpp:131-172
```

Source-backed fields:

```text
source_filename
output_ext
material_filename
forward_up_axes
unit_size
scale
physics_primitive
merge_all_nodes
scene_origin
ignore_custom_normals
ignore_uv
materials
nodes
autolodsettings
animation
jointPhysicsData
```

Node fields:

```text
CRYENGINE_Source-release/Code/Tools/RC/ResourceCompilerPC/FBX/ImportRequest.cpp:22-44
```

Source-backed node fields:

```text
path
name
udp
nodes
```

The same serializer also reads `CNodeProperties` inline. Those include physical node properties such as:

```text
mass
density
primitive
no_explosion_occlusion
stiffness
constraint_limit
constraint_collides
```

Material fields:

```text
CRYENGINE_Source-release/Code/Tools/RC/ResourceCompilerPC/FBX/ImportRequest.cpp:47-85
```

Source-backed material fields:

```text
name
physicalize
sub_index
```

Supported `physicalize` values:

```text
no
default
obstruct
no_collide
proxy_only
```

`sub_index` rule:

```text
sub_index >= MAX_SUB_MATERIALS(128) -> -1
sub_index < 0 means delete faces with this material
```

Supported output extensions:

```text
CRYENGINE_Source-release/Code/Tools/RC/ResourceCompilerPC/FBX/FbxConverter.cpp:2783-2790
```

```text
cgf
chr
skin
caf
i_caf
```

## What Changed

Added:

```text
output_formats/rc_import_schema.py
```

The module records:

```text
RC_IMPORT_ROOT_FIELDS
RC_IMPORT_NODE_FIELDS
RC_IMPORT_MATERIAL_FIELDS
RC_IMPORT_JOINT_PHYSICS_FIELDS
RC_IMPORT_PHYSICALIZE_VALUES
RC_IMPORT_OUTPUT_EXTENSIONS
RC_IMPORT_MAX_SUB_MATERIALS
```

and helper functions:

```text
collect_unknown_request_fields(request)
normalize_rc_sub_index(sub_index)
```

Updated:

```text
output_formats/rc_request_builder.py
```

The builder still detects proxy-like node names internally so it can generate `jointPhysicsData`, but it no longer writes unsupported node fields:

```text
lod
bIsProxy
helper
```

Those names are not read by `ImportRequest.cpp` for request nodes. Leaving them in the JSON could make future tooling believe they were real RC schema fields.

## Current Converter Boundary

The converter now emits source-backed request node fields:

```json
{
  "name": "Chair_proxy",
  "path": ["Root", "Chair_proxy"]
}
```

and keeps proxy relation data in the source-backed `jointPhysicsData` array:

```json
{
  "jointNodePath": ["Root"],
  "proxyNodePath": ["Root", "Chair_proxy"],
  "snapToJoint": true
}
```

## Still Open

This phase defines request field names and removes unsupported node fields. It does not yet prove every semantic combination.

Open Phase 2 work:

```text
probe physics_primitive behavior
probe node CNodeProperties effects on generated CGF
probe animation request fields for chr/skin/caf/i_caf
replace guessed proxy naming heuristics with source/RC verified behavior
```

## Verification

Passed targeted verification:

```powershell
uv run python -m pytest tests\test_rc_request_builder.py tests\test_rc_smoke_test.py tests\test_model_export_context.py
uv run python -m compileall output_formats\rc_import_schema.py output_formats\rc_request_builder.py tests\test_rc_request_builder.py
```

New tests cover:

```text
request root fields stay source-backed
node JSON no longer contains unsupported lod/bIsProxy/helper fields
proxy-name detection still generates jointPhysicsData
physicalize/output extension constants are recorded
sub_index >= 128 normalizes to -1
```
