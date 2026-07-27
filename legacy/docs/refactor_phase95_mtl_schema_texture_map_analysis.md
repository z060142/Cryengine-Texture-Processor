# Refactor Phase 95: MTL Schema Texture Map Analysis

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Teach the `.mtl` schema report to classify real `<Texture Map=... File=...>`
entries against the source-backed CryEngine texture map and suffix policy.

Earlier phases made exporter texture mapping visible in
`material_diagnostics.json`. This phase brings the same policy into
`tools/mtl_schema_report.py`, so existing CryEngine `.mtl` samples can be
scanned and compared against converter output.

## Code Changes

Added to `output_formats/cryengine_mtl_schema.py`:

```text
CE_TEXTURE_MAP_NAMES
analyze_ce_texture_map_entry(...)
```

Updated `tools/mtl_schema_report.py`:

```text
texture entries now include texture_map_analysis
schema summary now includes texture_map_policy_reasons
schema summary now includes texture_map_unknowns
schema summary now includes texture_suffix_statuses
schema summary now includes texture_expected_suffixes
```

## Classifications

Texture map policy reasons:

```text
source_backed_ce_map
unknown_ce_map_type
missing_ce_map_type
```

Suffix statuses are reused from the shared suffix policy:

```text
matches_expected_suffix
mismatch_expected_suffix
no_source_backed_suffix
not_applicable
```

## Why This Matters

When we scan real `.mtl` files, we can now answer questions such as:

```text
Which CE Texture Map names actually appear?
Which maps are unknown to our source-backed table?
Which texture files match CE suffix conventions?
Which suffix mismatches are common enough to need importer repair?
```

That is directly useful for the future Blender plugin and custom converter
schema because it separates source-backed map names from project-specific or
legacy map names.

## Boundary

This phase does not change `.mtl` export behavior.

It only improves evidence extraction from existing material files.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_cryengine_mtl_schema.py tests\test_mtl_schema_report.py
```

Result:

```text
20 passed
```
