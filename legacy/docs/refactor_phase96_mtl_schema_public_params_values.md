# Refactor Phase 96: MTL Schema PublicParams Value Analysis

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Make `tools/mtl_schema_report.py` more useful for studying real
`PublicParams` usage in CryEngine `.mtl` files.

Earlier phases proved how CryEngine parses `PublicParams` values as vector-like
shader params. This phase adds grouped raw-value and component-count summaries
so real material samples can show which parameters are common, what values they
use, and whether they behave like scalar, vec3, or vec4 data.

## Code Changes

Updated `tools/mtl_schema_report.py` schema summary with:

```text
public_param_values
public_param_values_by_name
public_param_component_counts_by_name
```

Existing per-material data still includes:

```text
public_params
public_param_analysis
```

## Why This Matters

`PublicParams` are shader-dependent. There is no single global fixed schema for
every material.

The new report summaries let us answer:

```text
Which PublicParams names appear in real samples?
Which raw values are common for each parameter?
Which parameters are usually scalar, vec3, or vec4?
Which exporter compatibility params are actually seen in source/editor output?
```

This directly supports later Phase 2 work on replacing compatibility
`PublicParams` defaults with source-derived or round-trip-proved values.

## Boundary

This phase does not change `.mtl` export behavior.

It only improves evidence extraction from existing material files.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_mtl_schema_report.py tests\test_cryengine_mtl_schema.py
```

Result:

```text
20 passed
```
