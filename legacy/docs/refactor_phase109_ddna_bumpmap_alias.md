# Phase 109 - DDNA Bumpmap Alias

## Why this exists

Phase 108 added RC texture source extension checks and CE texture suffix
diagnostics. That exposed a false-positive risk: CryEngine's material helper
table names the Bumpmap suffix `_ddn`, but real CE texture compiler paths also
distinguish `_ddna` normal-alpha textures.

For our converter this matters because generated or sample `.mtl` files can
legitimately put a `_ddna` texture in a `Map="Bumpmap"` slot. Treating that as a
suffix mismatch makes valid normal-alpha output look broken.

## Source-backed rule

Primary CE material helper suffix:

- `Bumpmap -> _ddn`
- source: `Code/CryEngine/Cry3DEngine/MaterialHelpers.cpp`

Accepted Bumpmap alias:

- `Bumpmap -> _ddna`
- source: `Code/CryEngine/RenderDll/Common/Textures/TextureCompiler.cpp`
- evidence: the texture compiler has separate delayed/error placeholders and
  checks for `_ddna.` before `_ddn.`

This does not change exported filenames. It only changes diagnostics.

## Diagnostic statuses

`analyze_ce_texture_suffix("Bumpmap", path)` now returns:

- `matches_expected_suffix`
  - filename stem ends with `_ddn`
  - `matched_suffix == "_ddn"`
- `matches_accepted_alias_suffix`
  - filename stem ends with `_ddna`
  - `matched_suffix == "_ddna"`
- `mismatch_expected_suffix`
  - filename stem ends with neither `_ddn` nor `_ddna`

The returned payload now includes:

- `expected_suffix`
- `accepted_suffixes`
- `matched_suffix`
- `suffix_status`

For Bumpmap, `expected_suffix` remains `_ddn`, while `accepted_suffixes` is
`["_ddn", "_ddna"]`.

## Practical impact

The material diagnostics exporter no longer emits `mismatch_ce_texture_suffix`
for `normal -> *_ddna.tif` or `normal -> *_ddna.dds`.

The `.mtl` schema report records `_ddna` Bumpmap textures as
`matches_accepted_alias_suffix`, so sample audits can separate true suffix
problems from normal-alpha textures.

## Current boundary

This phase does not decide whether the converter should always generate `_ddn`
or `_ddna`. Existing exporters can continue producing `_ddna` when gloss alpha
is packed with normals. The important rule is that `_ddna` in a Bumpmap slot is
not automatically a bug.

## Verification

- `uv run python -m pytest tests/test_cryengine_mtl_schema.py tests/test_material_diagnostics_exporter.py tests/test_mtl_schema_report.py`
