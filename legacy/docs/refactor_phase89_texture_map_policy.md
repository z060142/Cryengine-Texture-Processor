# Refactor Phase 89: Source-Backed Texture Map Policy

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Make the input texture type to CryEngine `.mtl` `<Texture Map=...>` mapping
explicit, shared, and visible in diagnostics.

The exporter already used `CE_TEXTURE_MAP_TYPES`, but the rule was just a
dictionary lookup. Known internal channels such as `ao` and `glossiness` were
silently skipped because CryEngine `.mtl` has no direct `Texture Map` entry for
them in the current schema table.

## Source Evidence

CryEngine source:

```text
CRYENGINE_Source-release/Code/CryEngine/Cry3DEngine/MaterialHelpers.cpp
```

Current source-backed mappings include:

```text
diffuse      -> Diffuse
normal       -> Bumpmap
specular     -> Specular
displacement -> Heightmap
opacity      -> Opacity
emissive     -> Emittance
subsurface   -> SubSurface
translucency -> Translucency
```

Known internal channels that do not emit `.mtl` `<Texture>` entries:

```text
ao
glossiness
```

## Code Changes

Added to `output_formats/cryengine_mtl_schema.py`:

```text
CE_TEXTURE_MAP_SOURCE
resolve_ce_texture_map(...)
exported_texture_map_policy(...)
```

`resolve_ce_texture_map(...)` classifies each texture reference as:

```text
source_backed_texture_map
known_internal_non_mtl_channel
missing_texture_path
unknown_texture_type
```

Updated shared callers:

```text
output_formats/mtl_exporter.py
model_processing/material_converter.py
output_formats/material_diagnostics_exporter.py
```

## Diagnostics

Each material row in `material_diagnostics.json` now includes:

```text
mtl_texture_map_policy
```

The root report now includes:

```text
mtl_texture_map_policy_summary
```

with:

```text
material_count
input_texture_type_counts
exported_ce_map_counts
skipped_reason_counts
source_evidence
```

This lets Blender/plugin tooling see exactly which input texture keys will
become CryEngine `.mtl` texture maps and which ones are ignored by the current
schema.

## Boundary

This phase does not change exporter behavior.

It preserves the existing rule that `ao` and `glossiness` are not emitted as
`.mtl` `<Texture>` entries. It only makes that skip explicit and machine
testable.

Shader `GenMask`, `StringGenMask`, and `PublicParams` generation are still
separate Phase 2 targets.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_cryengine_mtl_schema.py tests\test_mtl_exporter.py tests\test_material_converter.py tests\test_material_diagnostics_exporter.py
```

Result:

```text
63 passed
```
