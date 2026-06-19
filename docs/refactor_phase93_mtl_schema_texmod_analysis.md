# Refactor Phase 93: MTL Schema TexMod Analysis

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Teach the `.mtl` schema report to classify `TexMod` usage in real material
files.

Phase 92 made the exporter `TexMod` attributes a shared policy. This phase uses
that policy when scanning existing `.mtl` files so real samples can be compared
against the converter's current compatibility output.

## Source Evidence

CryEngine source:

```text
CRYENGINE_Source-release/Code/CryEngine/Cry3DEngine/MaterialHelpers.cpp
lines 263-324
```

Important behavior:

```text
MaterialHelpers saves a TexMod child only when the texture modifier differs
from CryEngine's default modifier.
```

## Code Changes

Updated `tools/mtl_schema_report.py`:

```text
texture entries now include texmod_analysis
schema summary now includes texmod_statuses
schema summary now includes texmod_attributes
schema summary now includes texmod_extra_attributes
```

`texmod_analysis.status` values:

```text
missing_texmod
matches_export_minimal_texmod
partial_export_minimal_texmod
custom_texmod
```

## Interpretation

`missing_texmod` means the texture has no `TexMod` child.

`matches_export_minimal_texmod` means it exactly matches the current exporter
compatibility output:

```text
TexMod_RotateType=0
TexMod_TexGenType=0
TexMod_bTexGenProjected=0
```

`partial_export_minimal_texmod` means only some of those default attributes are
present and none contradict the exporter defaults.

`custom_texmod` means the material contains custom modifier data, such as
different default values or extra attributes like tiling/offset fields.

## Boundary

This phase does not change `.mtl` export behavior.

It only improves evidence extraction from existing material files, which is
needed before deciding whether the converter should keep emitting minimal
TexMod nodes or omit them when defaults are used.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_mtl_schema_report.py tests\test_cryengine_mtl_schema.py
```

Result:

```text
19 passed
```
