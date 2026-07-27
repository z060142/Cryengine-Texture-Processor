# Refactor Phase 90: Texture Suffix Diagnostics

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Expose CryEngine texture filename suffix expectations through the shared `.mtl`
texture map policy and material diagnostics.

Phase 89 made texture type to `.mtl` `Texture Map` conversion explicit. This
phase adds a second layer: once a texture is mapped to a CryEngine `Map` name,
diagnostics now report whether its filename already matches the source-backed
suffix convention.

## Source Evidence

CryEngine source:

```text
CRYENGINE_Source-release/Code/CryEngine/Cry3DEngine/MaterialHelpers.cpp
```

Current source-backed suffix examples:

```text
Diffuse    -> _diff
Bumpmap    -> _ddn
Specular   -> _spec
Smoothness -> _ddna
Heightmap  -> _displ
Emittance  -> _em
```

Not every exported map has a known suffix in the current table. For example,
`Opacity` is exported as a CE texture map, but it currently reports
`no_source_backed_suffix`.

## Code Changes

Added to `output_formats/cryengine_mtl_schema.py`:

```text
CE_TEXTURE_SUFFIX_SOURCE
analyze_ce_texture_suffix(...)
```

`resolve_ce_texture_map(...)` now adds:

```text
suffix_analysis
```

with:

```text
expected_suffix
suffix_status
filename
source_evidence
```

Possible `suffix_status` values:

```text
matches_expected_suffix
mismatch_expected_suffix
no_source_backed_suffix
not_applicable
```

`material_diagnostics.json` root summary now includes:

```text
mtl_texture_map_policy_summary.expected_suffix_counts
mtl_texture_map_policy_summary.suffix_status_counts
```

## Boundary

This phase does not rename textures and does not block export.

Suffix mismatch is diagnostic evidence only. That keeps current behavior stable
while giving the future Blender plugin and converter enough data to decide when
to rename, repack, or warn.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_cryengine_mtl_schema.py tests\test_material_diagnostics_exporter.py tests\test_mtl_exporter.py tests\test_material_converter.py
```

Result:

```text
64 passed
```
