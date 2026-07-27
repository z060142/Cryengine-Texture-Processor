# Refactor Phase 34: Saved Globals Mask Table

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Use CryEngine's generated shader `globals.txt` cache as a first-class evidence source for `.mtl` `StringGenMask` to `GenMask` checks.

Phase 33 rebuilt the common global table from `Engine/Shaders/*.ext`, but real persisted engine `.mtl` samples still did not match. This phase verifies the next obvious candidate: the runtime `Shaders/Cache/globals.txt` file loaded by the renderer.

## Source Evidence

`ShaderCore.cpp` writes generated globals with:

```text
FX_CACHE_VER <version>
<shader remap list>

%TOKEN <hex mask>
```

The save path uses `%I64x` / `%llx`, so masks are hexadecimal without a `0x` prefix.

`mfInitCommonGlobalFlags()` loads:

```text
<user path>/Shaders/Cache/globals.txt
```

If the file exists and the cache version is current, CryEngine reads every `%TOKEN HEX_MASK` line into `m_pShaderCommonGlobalFlag`. If the file is missing or stale, it rebuilds the table from shader `.ext` files and writes a fresh `globals.txt`.

## What Changed

Added to:

```text
tools/cryengine_shader_flags.py
```

New helpers:

```text
parse_common_global_flags_text(globals_text)
load_common_global_flag_table(globals_path)
```

Updated:

```text
tools/mtl_mask_report.py
```

New option:

```powershell
--globals-file "S:\Crytek\crytek\cryengine-gamesdk-sample-project\5.7.1\user\shaders\cache\globals.txt"
```

When both `--globals-file` and `--shader-ext-dir` are supplied, the saved globals file wins because it is the table CryEngine actually loads for that project cache.

## Local Cache Check

Checked these generated cache files:

```text
S:\Crytek\crytek\cryengine-gamesdk-sample-project\5.7.1\user\shaders\cache\globals.txt
S:\Crytek\crytek\cryengine-gamesdk-sample-project\5.7.1\user(1)\shaders\cache\globals.txt
S:\Crytek\crytek\cryengine-gamesDK-sample-project-legacy\5.7.1\user\shaders\cache\globals.txt
S:\Crytek\crytek\TPS_Demo\My Project\user\shaders\cache\globals.txt
```

All four had 51 parsed tokens and identical key values:

```text
%NORMAL_MAP                0x20
%VERTCOLORS                0x2000000000
%SPECULAR_MAP              0x2000000000000
%SUBSURFACE_SCATTERING     0x4000000000000
%ALLOW_SILHOUETTE_POM      missing
```

## Real Sample Report

Generated:

```text
docs/phase34_mtl_mask_saved_globals_samples.json
```

Command:

```powershell
uv run python -m tools.mtl_mask_report "S:\Crytek\crytek\CRYENGINE_Source-release\Engine\EngineAssets\Materials\material_default.mtl" "S:\Crytek\crytek\CRYENGINE_Source-release\Editor\Objects\mtlobjects.mtl" "S:\Crytek\crytek\CRYENGINE_Source-release\Engine\EngineAssets\Materials\MeshImporter\MI_PreviewVertexColor.mtl" --globals-file "S:\Crytek\crytek\cryengine-gamesdk-sample-project\5.7.1\user\shaders\cache\globals.txt" --output docs\phase34_mtl_mask_saved_globals_samples.json
```

Summary:

```json
{
  "file_count": 3,
  "material_count": 3,
  "tokenized_material_mismatch_count": 3,
  "unknown_illum_token_count": 1,
  "unknown_common_global_legacy_fix_token_count": 5,
  "unknown_common_global_generated_token_count": 1,
  "common_global_generated_match_count": 0
}
```

Important mismatches:

```text
material_default.mtl
StringGenMask = %SUBSURFACE_SCATTERING
persisted GenMask = 0x80000000
saved globals mask = 0x4000000000000

MI_PreviewVertexColor.mtl
StringGenMask = %SUBSURFACE_SCATTERING%VERTCOLORS
persisted GenMask = 0x2020000000
saved globals mask = 0x4002000000000

mtlobjects.mtl
StringGenMask = %ALLOW_SILHOUETTE_POM%SPECULAR_MAP%SUBSURFACE_SCATTERING
persisted GenMask = 0xC0000001
saved globals known-token mask = 0x6000000000000
%ALLOW_SILHOUETTE_POM is not present in the saved globals table.
```

## Rule

The exporter should not blindly rewrite persisted `.mtl` `GenMask` using the current `globals.txt` table.

The saved `globals.txt` file is the best evidence for how a running 5.7.1 renderer maps common-global `StringGenMask` tokens, but the inspected persisted EngineAssets samples still appear to come from another mask domain or older material/shader history.

For generated assets, the safest current behavior remains:

```text
preserve known compatibility values until RC / Material Editor round-trip behavior is proven
```

For diagnostics and future conversion logic, use this precedence:

```text
project globals.txt > rebuilt Engine/Shaders/*.ext table > static compatibility table
```

## Remaining Work

- Probe Material Editor or RC round-trips: save a material with only `StringGenMask`, only `GenMask`, and mismatched values, then inspect the resulting `.mtl`.
- Find whether `GenMask = 0x80000000` for `%SUBSURFACE_SCATTERING` comes from an older Illum/local shader property mask path, a legacy persisted value, or an import/export compatibility remap.
- Trace `EF_GetShaderGlobalMaskGenFromString()` through shader remap-list behavior for non-common-global shaders.
- Extend exporter policy only after we know which field RC trusts during FBX import: persisted numeric `GenMask`, `StringGenMask`, or shader-derived recomputation.

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_cryengine_shader_flags.py tests\test_mtl_mask_report.py tests\test_cryengine_mtl_schema.py
```

New tests cover:

- parsing `globals.txt` while skipping `FX_CACHE_VER` and the shader remap list
- loading a saved globals table from disk
- preferring `--globals-file` over `--shader-ext-dir` in `.mtl` mask reports
