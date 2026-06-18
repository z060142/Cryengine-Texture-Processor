# Refactor Phase 32: MTL Mask Sample Report

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Create a repeatable way to compare real CryEngine `.mtl` files against our current mask knowledge.

Phase 31 proved the source locations for:

- `.mtl` texture map names
- Illum shader extension token masks
- exporter compatibility mask values

This phase adds a report tool to compare those tables against actual `.mtl` samples.

## What Changed

Added:

```text
tools/mtl_mask_report.py
```

The tool parses `.mtl` files and reports, per material:

- `GenMask` literal
- chosen parsed value and parse base
- ambiguous bare numeric values
- `StringGenMask` tokens
- Illum.ext token OR value
- ShaderCore common global legacy-fix OR value
- current exporter compatibility OR value
- whether the persisted `GenMask` matches any known table

It can scan files or directories:

```powershell
uv run python -m tools.mtl_mask_report path\to\file.mtl
uv run python -m tools.mtl_mask_report path\to\folder --limit 20 --output report.json
```

## Source Evidence Added

`output_formats.cryengine_mtl_schema` now also records selected common global legacy-fix masks from:

```text
S:\Crytek\crytek\CRYENGINE_Source-release\Code\CryEngine\RenderDll\Common\Shaders\ShaderCore.cpp
```

Important source behavior:

- `.ext` files with `UsesCommonGlobalFlags` contribute token names to a global table.
- ShaderCore can remap common global flags through legacy-fix values.
- `StringGenMask` is parsed by common/global shader code, not by the Illum `.ext` table alone.

## Real Sample Report

Generated:

```text
docs/phase32_mtl_mask_real_samples.json
```

Command:

```powershell
uv run python -m tools.mtl_mask_report "S:\Crytek\crytek\CRYENGINE_Source-release\Engine\EngineAssets\Materials\material_default.mtl" "S:\Crytek\crytek\CRYENGINE_Source-release\Editor\Objects\mtlobjects.mtl" "S:\Crytek\crytek\CRYENGINE_Source-release\Engine\EngineAssets\Materials\MeshImporter\MI_PreviewVertexColor.mtl" --output docs\phase32_mtl_mask_real_samples.json
```

Summary:

```json
{
  "file_count": 3,
  "material_count": 3,
  "tokenized_material_mismatch_count": 3,
  "unknown_illum_token_count": 1,
  "unknown_common_global_legacy_fix_token_count": 5
}
```

Key sample:

```text
material_default.mtl
StringGenMask = %SUBSURFACE_SCATTERING
GenMask       = 80000000
Illum.ext OR  = 0x80000
export compat = 0x20
```

This proves that persisted CryEngine sample `GenMask` values are not simply the local Illum `.ext` token OR.

Another sample:

```text
MI_PreviewVertexColor.mtl
StringGenMask = %SUBSURFACE_SCATTERING%VERTCOLORS
GenMask       = 2020000000
```

The `VERTCOLORS` token has a ShaderCore common global legacy-fix value, but the whole persisted `GenMask` still needs the complete common-global/remap path to reproduce exactly.

## Rule

Do not replace exporter `GenMask` values directly with `ILLUM_EXT_SHADER_MASKS`.

Current evidence says the correct path is:

```text
StringGenMask tokens -> renderer/common global flag remap -> persisted GenMask
```

The exporter should keep compatibility values until we either:

- reproduce the remap table completely, or
- prove that RC/CE safely recomputes from `StringGenMask` and ignores a stale `GenMask`.

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_mtl_mask_report.py tests\test_cryengine_mtl_schema.py tests\test_mtl_exporter.py
```

New tests cover:

- token extraction from concatenated `StringGenMask`
- unknown-token reporting
- ambiguous bare numeric `GenMask` parsing
- decimal parsing for exporter-style values
- report summaries
- common global legacy-fix matching for `%VERTCOLORS`

## Remaining Work

- Find or generate the complete common global flag table used by this engine build.
- Probe whether RC recomputes `GenMask` from `StringGenMask` during import.
- Decide whether exporter should emit `GenMask`, omit it, or write a recomputed value.
- Add a warning/report field for materials whose exported `GenMask` is compatibility-only.
