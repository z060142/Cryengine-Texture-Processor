# Refactor Phase 35: RC GenMask Acceptance Probe

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Find out whether CryEngine Resource Compiler FBX import rejects, rewrites, or warns about `.mtl` `GenMask` / `StringGenMask` combinations.

Phase 34 showed that current 5.7.1 `Shaders/Cache/globals.txt` still does not explain persisted EngineAssets `.mtl` `GenMask` values. The next question was whether RC itself trusts or validates those fields during FBX conversion.

## What Changed

Added:

```text
tools/mtl_genmask_probe.py
```

The probe:

1. creates normal RC FBX smoke bundles through the existing `prepare_smoke_bundle()` path
2. mutates the generated `.mtl` file only
3. runs RC for each material-mask variant
4. records output existence, RC return code, material before/after attributes, and any real `GenMask` / `StringGenMask` / `Shader` log lines

Default variants:

```text
exporter_baseline
string_only_subsurface
gen_only_legacy_subsurface
legacy_gen_with_string
runtime_globals_gen_with_string
no_mask_fields
```

## Real RC Probe

Generated:

```text
docs/phase35_mtl_genmask_rc_probe.json
```

Work files:

```text
S:\Crytek\crytek\Stripped to the bone\mtl_genmask_probe_work_phase35
```

Command:

```powershell
uv run python -m tools.mtl_genmask_probe --work-dir "S:\Crytek\crytek\Stripped to the bone\mtl_genmask_probe_work_phase35" --asset-name "Phase35GenMaskProbe" --output docs\phase35_mtl_genmask_rc_probe.json
```

Input evidence:

```text
rc.exe = S:\Crytek\crytek\cryengine-57-lts\5.7.1\Tools\rc\rc.exe
FBX    = S:\Crytek\crytek\cryengine-gamesdk-sample-project\5.7.1\gamesdk\objects\cubao\CubeA.fbx
```

Summary:

```json
{
  "variant_count": 6,
  "success_count": 6,
  "failure_count": 0,
  "mask_related_log_hit_count": 0,
  "rc_accepts_all_variants": true
}
```

Each variant produced a `.cgf` with RC return code `0`.

Important accepted cases:

```text
StringGenMask only, GenMask removed
GenMask only, StringGenMask removed
GenMask = 0x80000000 with StringGenMask = %SUBSURFACE_SCATTERING
GenMask = 0x4000000000000 with StringGenMask = %SUBSURFACE_SCATTERING
both fields removed
```

## Rule

For FBX-to-CGF import, RC acceptance does not prove `.mtl` shader-mask correctness.

This probe shows RC 5.7.1 accepts all tested `GenMask` / `StringGenMask` combinations and emits no relevant shader-mask diagnostics. Therefore:

```text
RC FBX import appears to require material slot/name alignment, not shader-mask validity.
```

The current exporter should keep focusing RC conversion correctness on:

```text
FBX material table -> request materials -> MTL sub-material order -> CGF MeshSubsets.nMatID
```

`GenMask` generation remains a separate material-runtime problem and should not be considered solved by a successful RC import.

## Remaining Work

- Probe Material Editor reload/save behavior for the same variants.
- Probe runtime material loading if a lightweight game/editor launch path can be automated.
- Decide exporter policy after Material Editor evidence:
  - omit numeric `GenMask` and rely on `StringGenMask`
  - write compatibility-preserved values
  - write project `globals.txt` values
  - maintain a versioned compatibility map for older persisted material masks
- Add UI diagnostics that warn when RC conversion succeeds but material shader-mask evidence is still unverified.

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_mtl_genmask_probe.py tests\test_rc_smoke_test.py tests\test_rc_import_runner.py tests\test_mtl_mask_report.py
uv run python -m tools.mtl_genmask_probe --work-dir "S:\Crytek\crytek\Stripped to the bone\mtl_genmask_probe_work_phase35" --asset-name "Phase35GenMaskProbe" --output docs\phase35_mtl_genmask_rc_probe.json
```

New tests cover:

- `.mtl` mask attribute mutation
- mask-related RC log filtering without path-name false positives
- probe report generation through a fake RC runner
- missing RC reporting
