# Refactor Phase 88: Material Diagnostics MTL Flags Policy

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Carry the source-backed `.mtl` `MtlFlags` rules into the normal material
diagnostics sidecar.

Phase 86 made exporter default flags source-backed. Phase 87 made report tools
decode flags from real `.mtl` files. This phase exposes the same rule through
`material_diagnostics.json`, so model export diagnostics can be inspected
without running a separate MTL report.

## Source Evidence

CryEngine source:

```text
CRYENGINE_Source-release/Code/CryEngine/CryCommon/Cry3DEngine/IMaterial.h
lines 46-77
```

Current exporter defaults remain:

```text
root Material: 524544 = MTL_FLAG_MULTI_SUBMTL + MTL_64BIT_SHADERGENMASK
sub Material:  524416 = MTL_FLAG_PURE_CHILD + MTL_64BIT_SHADERGENMASK
```

## Code Changes

Added to `output_formats/cryengine_mtl_schema.py`:

```text
exported_mtl_flags_policy()
```

The helper returns:

```text
root_material
sub_material
source_evidence
```

Each material row in `material_diagnostics.json` now includes:

```text
mtl_flags_policy
```

The root report now includes:

```text
mtl_flags_policy_summary
```

with:

```text
material_count
root_material
sub_material_flag_counts
sub_material_flag_name_counts
source_evidence
```

## Boundary

This phase does not change `.mtl` XML output.

It only exposes the source-backed flags policy in diagnostics. Shader
`GenMask`, `StringGenMask`, and `PublicParams` remain separate Phase 2 targets.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_cryengine_mtl_schema.py tests\test_material_diagnostics_exporter.py tests\test_mtl_exporter.py
```

Result:

```text
50 passed
```
