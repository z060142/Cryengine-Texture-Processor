# Refactor Phase 94: MTL Schema Attribute Policy Analysis

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Teach the `.mtl` schema report to compare real material attributes against the
converter's current exporter attribute policy.

Phase 91 exposed the exporter material attribute defaults in
`material_diagnostics.json`. This phase brings the same policy into
`tools/mtl_schema_report.py` so real `.mtl` samples can be scanned for
attribute differences.

## Why This Matters

The converter still writes compatibility values such as:

```text
Shininess=255
Specular=1,1,1
Emittance=0,0,0,0
```

Some of these are source-aligned, while others still need round-trip evidence.
The schema report can now show whether real CE materials usually omit, match,
or differ from these values.

## Code Changes

Updated `tools/mtl_schema_report.py`:

```text
material records now include attribute_policy_analysis
schema summary now includes material_attribute_policy_statuses
schema summary now includes material_attribute_policy_missing
schema summary now includes material_attribute_policy_differences
```

Per-attribute statuses:

```text
matches_export_attribute
missing_export_attribute
differs_from_export_attribute
```

## Interpretation

`matches_export_attribute` means the real `.mtl` attribute exactly matches the
current exporter policy.

`missing_export_attribute` means the real `.mtl` material omits an attribute
that the exporter currently writes.

`differs_from_export_attribute` means the real material writes the attribute
with a different value. This is especially important for fields like
`Shininess`, where visible Sandbox defaults differ from the current exporter
compatibility value.

## Boundary

This phase does not change `.mtl` export behavior.

It only improves evidence extraction from existing material files, so later
Phase 2 work can decide which compatibility values should be replaced with
source-derived or round-trip-proved values.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_mtl_schema_report.py tests\test_cryengine_mtl_schema.py
```

Result:

```text
19 passed
```
