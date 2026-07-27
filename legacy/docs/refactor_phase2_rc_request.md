# Refactor Phase 2: RC Import Request JSON

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Move the model JSON export away from the old editor-style approximation and toward the Resource Compiler input that `rc.exe` actually reads.

The important rule from the CryEngine source notes is:

- RC reads a root object named `request`.
- The editor metadata writer may use `metadata`, but external tools should emit `request`.

## What Changed

- Added `output_formats/rc_request_builder.py`.
- Replaced the old bulky `output_formats/json_exporter.py` with a thin file writer around the request builder.
- `export_json()` now writes:

```json
{
  "request": {
    "source_filename": "model.fbx",
    "output_ext": "cgf"
  }
}
```

- Transitional editor-style output is still available through:

```python
export_json(..., wrapper_name="metadata")
```

- RC material entries now contain only RC-facing fields:
  - `name`
  - `physicalize`
  - `sub_index`

- Removed editor-only fields from generated material request entries:
  - `file`
  - `ui_name`
  - `ui_autoflag`

- Removed the non-RC top-level `use_32_bit_positions` field from the direct RC request payload.
- `main.py` now passes the exported FBX filename into `export_json()`. This fixes the bug where importing a non-FBX source such as OBJ could produce JSON pointing RC at the original OBJ instead of the generated FBX.

## Current Request Defaults

The current builder defaults are:

```text
output_ext: cgf
material_filename: source basename
unit_size: cm
scale: 1.0
forward_up_axes: -Y+Z
merge_all_nodes: false
scene_origin: false
ignore_custom_normals: false
ignore_uv: false
autolodsettings.GenerateAutomaticLODs: false
```

Material physicalization still follows the legacy heuristic:

```text
name contains proxy/phys/physics/collision/collider -> proxy_only
everything else -> no_collide
```

This is schema-correct, but it is not yet the full CryEngine Editor material assignment algorithm.

## Tests Added

`tests/test_rc_request_builder.py` covers:

- default wrapper is `request`
- transitional `metadata` wrapper still works
- generated material entries contain RC fields only
- duplicate Blender material suffixes are collapsed
- placeholder materials are skipped
- proxy materials become `proxy_only`
- node paths are emitted as arrays
- proxy nodes generate `jointPhysicsData`
- exported JSON points to the FBX filename supplied to `export_json()`

## Verification

Passed:

```powershell
python -m pytest tests
python -m compileall main.py output_formats tests
```

## Remaining RC Work

The JSON is now shaped like RC input, but the conversion logic is not complete yet.

Next high-value pieces:

- Implement true CryEngine material sub-index assignment:
  - match existing `.mtl` submaterials by name
  - preserve FBX material IDs when possible
  - fill free indices deterministically
  - encode deleted materials with `sub_index = -1`
- Add explicit export target selection for `cgf`, `chr`, `skin`, `caf`, and `i_caf`.
- Add `animation` request generation for CAF export.
- Add unit/axis options to the UI and pass them to the request builder.
- Replace node naming heuristics with the exact CryEngine/Blender path mapping once verified with sample FBX files.
- Run generated request JSON through a real `rc.exe` invocation against sample assets.
