# Refactor Phase 81: RC Request Required Fields

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 2 item: request JSON schema and RC import behavior

## Goal

Extend the RC-facing request schema gate so it distinguishes missing required fields from malformed values.

Phase 79 rejected unknown fields.
Phase 80 rejected malformed values for fields the converter already writes.
This phase adds a small required-field matrix for serializer fields that the converter must control before writing JSON for RC.

## Source Evidence

The current required-field matrix follows fields read directly by:

```text
Code/Tools/RC/ResourceCompilerPC/FBX/ImportRequest.cpp
```

Relevant serializer lines:

```text
SNodeInfoType: path, name
SMaterialInfo: name, physicalize, sub_index
CImportRequest: source_filename, output_ext
SJointPhysicsData: jointNodePath, proxyNodePath, snapToJoint
```

`material_filename` is intentionally not treated as required in this phase because the RC source assigns `"default"` when it is empty.

## What Changed

Extended:

```text
output_formats/rc_import_schema.py
```

Added required-field constants:

```text
RC_IMPORT_REQUIRED_ROOT_FIELDS
RC_IMPORT_REQUIRED_MATERIAL_FIELDS
RC_IMPORT_REQUIRED_NODE_FIELDS
RC_IMPORT_REQUIRED_JOINT_PHYSICS_FIELDS
```

Added stable diagnostics:

```text
rc_request_missing_root_field
rc_request_missing_material_field
rc_request_missing_node_field
rc_request_missing_joint_physics_field
```

The value gate now also validates:

```text
source_filename is a non-empty string when present
node name is a non-empty string when present
node path is an array when present
nested node children are arrays when present
jointNodePath and proxyNodePath are arrays when present
snapToJoint is a boolean when present
```

## Current Boundary

This phase still does not claim a complete RC schema implementation.

It does not yet validate:

```text
every physics/node numeric property
joint limit numeric values and ranges
animation field requirements for chr/skin/caf/i_caf
autolodsettings content
whether nodes/materials may be empty for every output extension
Material Editor round-trip behavior
material mask or shader parameter rules
```

The point is to stop the converter from writing request JSON that is obviously missing the serializer fields it depends on.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_rc_request_builder.py tests\test_rc_smoke_test.py tests\test_material_mapping_report.py
```

Result:

```text
77 passed
```

Full verification:

```powershell
uv run python -m pytest tests
uv run python -m compileall core model_processing output_formats tests tools ui ui_pyside utils main.py legacy_tk_main.py
uv lock --check
git diff --check
```

Result:

```text
294 passed
compileall succeeded
uv lock --check succeeded
git diff --check succeeded
```

New coverage proves:

```text
normal generated RC requests still have no schema diagnostics
missing root, material, node, and joint physics fields produce stable diagnostics
invalid node name/path/children values produce stable diagnostics
invalid joint physics path/snap values produce stable diagnostics
the RC-facing wrapper rejects missing required fields before export
RC smoke and material mapping report tests remain compatible with the stricter gate
```
