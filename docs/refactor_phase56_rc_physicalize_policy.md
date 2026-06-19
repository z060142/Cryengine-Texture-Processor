# Refactor Phase 56: RC Physicalize Policy

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 2 item: request material mapping and material physicalization

## Goal

Turn request material `physicalize` handling into a source-backed converter policy.

Before this phase, the request builder always chose `physicalize` from material names:

```text
proxy-like names -> proxy_only
everything else -> no_collide
```

That compatibility heuristic is still preserved as a fallback, but explicit material metadata now wins. This lets a future Blender plugin or custom conversion tool write the intended RC value directly instead of fighting the converter's name guessing.

## Source Evidence

RC accepts these request values:

```text
CRYENGINE_Source-release/Code/Tools/RC/ResourceCompilerPC/FBX/ImportRequest.cpp:53-79
```

```text
no         -> PHYS_GEOM_TYPE_NONE
default    -> PHYS_GEOM_TYPE_DEFAULT
obstruct   -> PHYS_GEOM_TYPE_OBSTRUCT
no_collide -> PHYS_GEOM_TYPE_NO_COLLIDE
proxy_only -> PHYS_GEOM_TYPE_DEFAULT_PROXY
unknown    -> PHYS_GEOM_TYPE_NONE
```

Sandbox Mesh Importer exposes matching UI labels:

```text
CRYENGINE_Source-release/Code/Sandbox/Plugins/MeshImporter/EditorMetaData.cpp:12-18
```

```text
no         -> render
default    -> render, collide, raytest
obstruct   -> render, collide
no_collide -> render, raytest
proxy_only -> collide, raytest
```

The FBX metadata serializer also names the same strings:

```text
CRYENGINE_Source-release/Code/Sandbox/Plugins/MeshImporter/FbxMetaData.cpp:22-28
```

## Important RC Behavior

Unknown `physicalize` strings do not fail closed.

`ImportRequest.cpp` maps any unrecognized value to `PHYS_GEOM_TYPE_NONE`, which is the same request value as:

```text
no
```

So a typo like:

```json
{"name": "Wall", "physicalize": "render_only", "sub_index": 0}
```

does not mean "render only" because RC has no such token. It becomes:

```json
{"name": "Wall", "physicalize": "no", "sub_index": 0}
```

The converter now mirrors that behavior and records a warning diagnostic.

## What Changed

Updated:

```text
model_processing/rc_material_policy.py
```

Added source-backed physicalize policy:

```text
RC_PHYSICALIZE_VALUES
RC_PHYSICALIZE_DISPLAY
normalize_rc_physicalize()
infer_rc_physicalize_from_name()
resolve_rc_physicalize()
rc_physicalize_diagnostics()
```

Updated:

```text
output_formats/rc_request_builder.py
```

Request material generation now resolves physicalize in this order:

```text
1. explicit material["physicalize"]
2. explicit material["physicalization"]
3. explicit material["physicalize_setting"]
4. existing name heuristic fallback
```

Invalid explicit values are normalized to `no`, and `include_diagnostics=True` adds:

```text
rc_unknown_physicalize_defaults_to_no
```

Updated:

```text
model_processing/material_manifest.py
```

Manifest material rows may now carry `physicalize`, so an FBX material-table sidecar can preserve user/plugin intent.

Updated:

```text
output_formats/material_diagnostics_exporter.py
```

Material diagnostics sidecars now include:

```text
physicalize
physicalize_source
requested_physicalize
```

and warn when RC would normalize an unknown value.

## Current Boundary

This phase does not replace the old name heuristic. It only demotes that heuristic to a fallback.

The fallback remains:

```text
names containing proxy/phys/physics/collision/collider -> proxy_only
everything else -> no_collide
```

This keeps current behavior stable while allowing source-backed explicit values to take over where available.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_rc_request_builder.py tests\test_material_diagnostics_exporter.py tests\test_material_manifest.py tests\test_material_index_assigner.py tests\test_rc_smoke_test.py
```

Result:

```text
54 passed
```

New coverage proves:

```text
explicit physicalize metadata is preserved in request materials
unknown physicalize values normalize to no like RC
unknown physicalize values emit diagnostics
manifest physicalize metadata overrides the old name heuristic
existing name heuristic behavior remains intact when no explicit value exists
```
