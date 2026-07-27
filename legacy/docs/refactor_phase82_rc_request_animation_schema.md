# Refactor Phase 82: RC Request Animation Schema

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 2 item: request JSON schema and RC import behavior

## Goal

Extend the RC-facing request schema gate to cover the source-backed `animation` object.

The converter still does not generate real CAF/CHR/SKIN animation requests. This phase only makes sure that if a request contains `animation`, the field names and basic value types match the CryEngine serializer before the JSON is written for RC.

## Source Evidence

`ImportRequest.cpp` serializes `CImportRequest::SAnimation` with:

```text
name
motionNodePath
startFrame
endFrame
```

Source locations:

```text
Code/Tools/RC/ResourceCompilerPC/FBX/ImportRequest.cpp:88-95
Code/Tools/RC/ResourceCompilerPC/FBX/ImportRequest.h:26-31
Code/Tools/RC/ResourceCompilerPC/FBX/ImportRequest.h:84-85
```

`ImportRequest.h` defines:

```text
name: string
motionNodePath: std::vector<string>
startFrame: int
endFrame: int
```

The request constructor initializes:

```text
startFrame = -1
endFrame = -1
```

So this phase accepts `-1` as the "use source animation stack bounds" sentinel.

## What Changed

Extended:

```text
output_formats/rc_import_schema.py
```

Added:

```text
RC_IMPORT_ANIMATION_FIELDS
```

Added diagnostics:

```text
rc_request_invalid_animation
rc_request_invalid_animation_name
rc_request_invalid_animation_motion_node_path
rc_request_invalid_animation_frame
rc_request_unknown_animation_field
```

Rules when `request.animation` is present:

```text
animation must be an object
name must be a string when present
motionNodePath must be an array when present
startFrame and endFrame must be integers >= -1 when present
only source-backed animation fields are allowed
```

## Current Boundary

This phase does not make animation export complete.

It does not yet validate:

```text
when animation is required for caf/i_caf/chr/skin
whether animation.name must match an FBX animation stack
whether motionNodePath resolves to a real source node
whether startFrame/endFrame are inside the FBX animation stack bounds
CAF/CHR/SKIN generation correctness
```

Those require probing `FbxConverter` behavior and/or running controlled animated fixtures through RC.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_rc_request_builder.py tests\test_rc_smoke_test.py tests\test_material_mapping_report.py tests\test_rc_import_runner.py
```

Result:

```text
87 passed
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
297 passed
compileall succeeded
uv lock --check succeeded
git diff --check succeeded
```

New coverage proves:

```text
source-backed animation fields pass schema diagnostics
invalid animation field types produce stable diagnostics
unknown animation fields are rejected by the RC-facing schema gate
wrap_import_request rejects invalid animation fields before export
normal RC smoke, mapping report, and request-runner tests remain compatible
```
