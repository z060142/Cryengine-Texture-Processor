# Refactor Phase 79: RC Request Schema Gate

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 2 item: request JSON schema and RC import behavior

## Goal

Start Phase 2 by turning the source-derived RC import request schema into an active gate for RC-facing JSON output.

Before this phase, the converter had:

```text
output_formats/rc_import_schema.py
collect_unknown_request_fields()
```

That helper could prove the generated request used only known fields, but it was passive. A later change could still accidentally put internal data such as `diagnostics` or `_is_proxy` into the final `{"request": ...}` JSON unless tests happened to notice.

## What Changed

Extended:

```text
output_formats/rc_import_schema.py
```

Added:

```text
collect_request_schema_diagnostics()
assert_rc_import_request_schema()
```

The diagnostics expose stable locations and codes for unknown RC request fields:

```text
rc_request_unknown_root_field
rc_request_unknown_node_field
rc_request_unknown_material_field
rc_request_unknown_joint_physics_field
rc_request_unknown_joint_limit_field
```

Updated:

```text
output_formats/rc_request_builder.py
```

`wrap_import_request(request, wrapper_name="request")` now validates the RC-facing request before returning:

```text
{"request": request}
```

The transitional `metadata` wrapper remains available and is not treated as an RC-facing payload.

## Current Boundary

This phase validates known field names only.

It does not yet replace or fully validate:

```text
field value types
required field matrix
per-output-extension request differences
complete RC request schema behavior
material mask or shader parameter rules
```

That keeps the change focused: internal converter evidence must not leak into the RC import JSON.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_rc_request_builder.py
```

Result:

```text
18 passed
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
287 passed
compileall succeeded
uv lock --check succeeded
git diff --check succeeded
```

New coverage proves:

```text
normal generated RC requests produce no schema diagnostics
root, node, material, joint physics, and joint limit unknown fields produce stable diagnostics
RC-facing request wrapping rejects source-unsupported fields before JSON export can write them
existing request JSON output shape is preserved for clean payloads
```
