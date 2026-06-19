# Refactor Phase 91: Material Attribute Policy Diagnostics

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Expose the exporter `.mtl` material attribute defaults as an explicit policy in
the normal material diagnostics sidecar.

The converter has long emitted values such as:

```text
Shader=Illum
Diffuse=1,1,1
Specular=1,1,1
Emittance=0,0,0,0
Opacity=1
Shininess=255
```

This phase does not change those exported values. It records which values are
aligned with visible CryEngine source evidence and which are still
compatibility-preserved until a Material Editor or RC round-trip proves the
final value.

## Source Evidence

CryEngine source:

```text
CRYENGINE_Source-release/Code/CryEngine/Cry3DEngine/MaterialHelpers.cpp
lines 638-652: loads Diffuse, Specular, Emittance, Shininess, Opacity, AlphaTest
lines 667-680: saves lighting attrs when different from renderer defaults
```

Sandbox source:

```text
CRYENGINE_Source-release/Code/Sandbox/EditorQt/Material/Material.cpp
lines 58-70: initializes Illum, Opacity=1, Diffuse=1,1,1,1, Smoothness=10
lines 1128-1139: saves MtlFlags, Shader, GenMask, StringGenMask, SurfaceType, MatTemplate
```

Runtime source:

```text
CRYENGINE_Source-release/Code/CryEngine/Cry3DEngine/MatMan.cpp
lines 1012-1019: default material creation sets Opacity=1 and Diffuse=1,1,1,1
```

## Code Changes

Added to `output_formats/cryengine_mtl_schema.py`:

```text
MTL_MATERIAL_ATTRIBUTE_POLICY
EXPORT_MATERIAL_ATTRIBUTE_STATUS
exported_material_attribute_policy()
```

Each material row in `material_diagnostics.json` now includes:

```text
mtl_attribute_policy
```

The root report now includes:

```text
mtl_attribute_policy_summary
```

with:

```text
material_count
attribute_value_counts
attribute_status_counts
source_evidence
```

## Current Attribute Status

Source-backed or source-aligned:

```text
Shader=Illum
Diffuse=1,1,1
Opacity=1
```

Loaded/saved by source, but current exporter default still needs round-trip
confirmation:

```text
Specular=1,1,1
Emittance=0,0,0,0
SurfaceType=
MatTemplate=
```

Compatibility-preserved because visible Sandbox default differs:

```text
Shininess=255
```

Sandbox initializes material smoothness to `10.0f`, while the current exporter
still writes `Shininess=255`. This phase makes that mismatch visible instead
of silently claiming it is final CryEngine behavior.

## Boundary

This phase does not change `.mtl` XML output.

It only adds diagnostic evidence so Phase 2 can replace compatibility defaults
with source-derived or round-trip-proved values later.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_cryengine_mtl_schema.py tests\test_material_diagnostics_exporter.py tests\test_mtl_exporter.py
```

Result:

```text
57 passed
```
