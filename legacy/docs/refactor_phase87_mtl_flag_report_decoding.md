# Refactor Phase 87: Decode MTL Flags In Material Reports

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Make CryEngine `.mtl` material flag evidence readable in reports.

Phase 86 replaced exporter magic numbers with named default flag
compositions. This phase extends that into the analysis tools so real `.mtl`
samples show which `EMaterialFlags` bits are present.

## Source Evidence

CryEngine source:

```text
CRYENGINE_Source-release/Code/CryEngine/CryCommon/Cry3DEngine/IMaterial.h
lines 46-77
```

The schema layer now includes the full `EMaterialFlags` table from that enum,
including:

```text
MTL_FLAG_PURE_CHILD
MTL_FLAG_MULTI_SUBMTL
MTL_FLAG_NODRAW
MTL_FLAG_COLLISION_PROXY
MTL_FLAG_SCATTER
MTL_FLAG_REQUIRE_FORWARD_RENDERING
MTL_64BIT_SHADERGENMASK
MTL_FLAG_REFRACTIVE
```

## Code Changes

Added/expanded in `output_formats/cryengine_mtl_schema.py`:

```text
complete MTL_FLAG_* constants from IMaterial.h
MTL_FLAG_NAMES
MTL_KNOWN_FLAG_MASK
describe_mtl_flags(...).unknown_mask
```

Added per-material `mtl_flags_analysis` to:

```text
tools/mtl_schema_report.py
tools/mtl_mask_report.py
```

`mtl_flags_analysis` contains:

```text
value
names
unknown_mask
source
lines
```

Added report summaries:

```text
schema.mtl_flag_names
schema.mtl_flag_unknown_masks
summary.mtl_flag_name_counts
summary.mtl_flag_unknown_mask_counts
```

## Why This Matters

Raw values like `524416` and `524544` are not useful when comparing exported
materials against real CryEngine materials.

The reports now show that:

```text
524544 -> MTL_FLAG_MULTI_SUBMTL + MTL_64BIT_SHADERGENMASK
524416 -> MTL_FLAG_PURE_CHILD + MTL_64BIT_SHADERGENMASK
```

If a real material uses a bit not covered by the current source-backed table,
`unknown_mask` will make that visible instead of silently dropping it.

## Boundary

This phase does not change exporter output.

It does not replace shader `GenMask`, `StringGenMask`, or `PublicParams`
generation. Those remain separate Phase 2 targets because their final values
still need renderer/editor round-trip evidence.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_cryengine_mtl_schema.py tests\test_mtl_schema_report.py tests\test_mtl_mask_report.py
```

Result:

```text
22 passed
```
