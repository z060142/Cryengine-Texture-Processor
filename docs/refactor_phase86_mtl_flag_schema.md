# Refactor Phase 86: Source-Backed MTL Flag Defaults

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Start Phase 2 by replacing one exporter magic-number seam with a source-backed
CryEngine material flag rule.

The `.mtl` exporter already emitted stable values:

```text
root Material MtlFlags: 524544
sub Material MtlFlags: 524416
```

This phase keeps those output values unchanged, but stops treating them as
opaque literals.

## Source Evidence

CryEngine source:

```text
CRYENGINE_Source-release/Code/CryEngine/CryCommon/Cry3DEngine/IMaterial.h
lines 46-77
```

Relevant flags:

```text
MTL_FLAG_PURE_CHILD     = 0x0080
MTL_FLAG_MULTI_SUBMTL   = 0x0100
MTL_64BIT_SHADERGENMASK = 0x80000
```

Exporter defaults now map to named compositions:

```text
root Material: MTL_64BIT_SHADERGENMASK | MTL_FLAG_MULTI_SUBMTL
sub Material:  MTL_64BIT_SHADERGENMASK | MTL_FLAG_PURE_CHILD
```

Decimal values remain:

```text
524544 = 0x80000 | 0x0100
524416 = 0x80000 | 0x0080
```

## Code Changes

Added to `output_formats/cryengine_mtl_schema.py`:

```text
MTL_FLAG_PURE_CHILD
MTL_FLAG_NAMES
MTL_ROOT_DEFAULT_FLAGS
MTL_SUB_MATERIAL_DEFAULT_FLAGS
compose_mtl_flags()
mtl_flags_attr()
describe_mtl_flags()
```

Changed:

```text
SUB_MATERIAL_DEFAULT_ATTRS["MtlFlags"]
build_mtl_document() root Material MtlFlags
```

Both now use the schema constants instead of raw decimal strings.

## Boundary

This phase does not change exported `.mtl` behavior.

It does not replace shader `GenMask`, `StringGenMask`, or `PublicParams`.
Those remain separate Phase 2 targets because their effective values still
depend on renderer/editor round-trip behavior.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_cryengine_mtl_schema.py tests\test_mtl_exporter.py
```

Result:

```text
21 passed
```
