# Refactor Phase 80: RC Request Value Gate

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 2 item: request JSON schema and RC import behavior

## Goal

Extend the RC-facing request schema gate from field names to the value shapes that most directly affect RC import behavior.

Phase 79 prevented internal converter fields from leaking into:

```text
{"request": ...}
```

This phase makes the same final wrapper gate reject malformed request values before the JSON is written for RC.

## What Changed

Extended:

```text
output_formats/rc_import_schema.py
```

Added:

```text
collect_request_value_diagnostics()
```

`collect_request_schema_diagnostics()` now combines:

```text
value and shape diagnostics
unknown field diagnostics
```

The gate now reports stable diagnostics for:

```text
rc_request_invalid_root
rc_request_invalid_output_ext
rc_request_invalid_collection
rc_request_invalid_material_row
rc_request_invalid_material_name
rc_request_invalid_material_physicalize
rc_request_invalid_material_sub_index
rc_request_invalid_node_row
rc_request_invalid_joint_physics_row
```

## RC-Facing Rules

The final request payload must use:

```text
output_ext in cgf, chr, skin, caf, i_caf
materials, nodes, and jointPhysicsData as arrays when present
materials[] entries as objects
materials[].name as a non-empty string
materials[].physicalize in no, default, obstruct, no_collide, proxy_only
materials[].sub_index as an integer from -1 through 127
nodes[] entries as objects
jointPhysicsData[] entries as objects
```

These checks are applied when wrapping with:

```python
wrap_import_request(request, wrapper_name="request")
```

## Current Boundary

This is still not a complete RC request schema rewrite.

It does not yet validate:

```text
every numeric node physics field
required field matrix for each output extension
animation/autolodsettings content
joint limit numeric ranges
Material Editor round-trip behavior
material mask or shader parameter rules
```

The purpose is narrower: the converter should not write obviously malformed RC request values for the fields it already controls.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_rc_request_builder.py tests\test_rc_smoke_test.py tests\test_material_mapping_report.py
```

Result:

```text
74 passed
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
291 passed
compileall succeeded
uv lock --check succeeded
git diff --check succeeded
```

New coverage proves:

```text
normal generated RC requests still pass schema diagnostics
invalid output_ext, material names, physicalize values, and sub_index values are rejected
invalid collection shapes and row types produce stable diagnostics
the RC-facing wrapper rejects invalid values before export_json can write them
export_json returns failure without writing malformed request JSON
RC smoke and material mapping report tests remain compatible with the stricter gate
```
