# Refactor Phase 37: Material Editor Round-Trip Harness

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Turn the next material-mask question into a repeatable Material Editor round-trip experiment.

Phase 36 proved from source that runtime/editor loading reads `GenMask` first, then lets `StringGenMask` remap it. The missing evidence is what the Material Editor writes after it loads and saves deliberately malformed or contradictory material masks.

## Source Evidence

Sandbox command line:

```text
Code/Sandbox/EditorQt/CryEdit.cpp
```

Relevant behavior:

```text
/runpython <script> -> general.run_file '<script>'
-project <cryproject> -> selects the project
```

Material Python API:

```text
Code/Sandbox/EditorQt/Material/MaterialPythonFuncs.cpp
```

Relevant behavior:

```text
material.get_property(path, "Material Settings/Surface Type")
material.set_property(path, "Material Settings/Surface Type", value)
```

`PySetProperty()` ends by calling:

```text
pMaterial->Update()
pMaterial->Save()
```

So a no-op `set_property` to the existing surface type should force a Material Editor load/save pass once the Sandbox Python script runs.

## What Changed

Added:

```text
tools/material_editor_roundtrip.py
```

Commands:

```powershell
uv run python -m tools.material_editor_roundtrip prepare --work-dir <dir>
uv run python -m tools.material_editor_roundtrip run --manifest <manifest> --timeout 120
uv run python -m tools.material_editor_roundtrip compare --manifest <manifest>
```

The tool:

1. creates six `.mtl` variants matching the Phase 35 mask cases
2. writes pristine input copies under the work directory
3. stages Editor-loadable materials under the GameSDK asset folder
4. writes a Sandbox `/runpython` script
5. records the exact Sandbox launch command
6. compares before/after material XML using `tools.mtl_schema_report`

## Generated Artifacts

Manifest:

```text
docs/phase37_material_editor_roundtrip_manifest.json
```

Initial compare:

```text
docs/phase37_material_editor_roundtrip_compare_initial.json
```

Sandbox run report:

```text
docs/phase37_material_editor_roundtrip_sandbox_run.json
```

Post-attempt compare:

```text
docs/phase37_material_editor_roundtrip_compare_after_sandbox.json
```

Work directory:

```text
S:\Crytek\crytek\Stripped to the bone\material_editor_roundtrip_phase37
```

Staged GameSDK materials:

```text
S:\Crytek\crytek\cryengine-gamesdk-sample-project\5.7.1\gamesdk\materials\codex_phase37_roundtrip
```

Sandbox script:

```text
S:\Crytek\crytek\Stripped to the bone\material_editor_roundtrip_phase37\run_material_roundtrip.py
```

Launch command:

```powershell
S:\Crytek\crytek\cryengine-57-lts\5.7.1\bin\win_x64\Sandbox.exe -project S:\Crytek\crytek\cryengine-gamesdk-sample-project\5.7.1\gamesdk.cryproject /BatchMode /runpython "S:\Crytek\crytek\Stripped to the bone\material_editor_roundtrip_phase37\run_material_roundtrip.py"
```

Phase 38 added a safer automated launch strategy named `sandbox_popen`, because `CryEdit.cpp` includes argv0 when it selects the first non-flag token for `/runpython`. Keep this command as the readable human form, but use `sandbox_popen` for automated runs.

## Current Run Result

Prepared cases:

```text
exporter_baseline
string_only_subsurface
gen_only_legacy_subsurface
legacy_gen_with_string
runtime_globals_gen_with_string
no_mask_fields
```

Initial compare:

```json
{
  "case_count": 6,
  "changed_count": 0,
  "unchanged_count": 6,
  "missing_after_count": 0,
  "sandbox_result_present": false
}
```

Sandbox run:

```json
{
  "state": "timeout",
  "returncode": 1,
  "result_exists": false
}
```

Post-attempt compare:

```json
{
  "case_count": 6,
  "changed_count": 0,
  "unchanged_count": 6,
  "missing_after_count": 0,
  "sandbox_result_present": false
}
```

Important interpretation:

```text
This is not evidence that Material Editor preserves the masks.
The Sandbox script did not produce sandbox_roundtrip_result.json within 120 seconds.
The staged .mtl files remained unchanged because the Material Editor round-trip did not complete.
```

No `Sandbox.exe` process was left running after the timeout attempt.

## Rule

Use this harness as the canonical Material Editor round-trip setup.

Do not change exporter `GenMask` policy until a run report has:

```text
state = result
result_exists = true
sandbox_result.results[*].success = true
```

Then compare:

```powershell
uv run python -m tools.material_editor_roundtrip compare --manifest docs\phase37_material_editor_roundtrip_manifest.json --output docs\phase37_material_editor_roundtrip_compare_after_sandbox.json
```

The decisive evidence will be the changed attributes in:

```text
GenMask
StringGenMask
MtlFlags
PublicParams
Textures/TexMod
```

## Remaining Work

- Find why this Sandbox build does not reach `/runpython` completion in batch mode within 120 seconds.
- Try a visible interactive Sandbox run and let the generated script finish, or increase timeout if the Editor is only slow.
- If `/runpython` remains unreliable, add a tiny Editor plugin or C++ command that loads and saves a material directly.
- Once a successful round-trip exists, update exporter mask policy from evidence instead of compatibility guesses.

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_material_editor_roundtrip.py tests\test_mtl_genmask_probe.py tests\test_mtl_schema_report.py
uv run python -m tools.material_editor_roundtrip prepare --work-dir "S:\Crytek\crytek\Stripped to the bone\material_editor_roundtrip_phase37" --output docs\phase37_material_editor_roundtrip_manifest.json
uv run python -m tools.material_editor_roundtrip compare --manifest docs\phase37_material_editor_roundtrip_manifest.json --output docs\phase37_material_editor_roundtrip_compare_initial.json
uv run python -m tools.material_editor_roundtrip run --manifest docs\phase37_material_editor_roundtrip_manifest.json --timeout 120 --output docs\phase37_material_editor_roundtrip_sandbox_run.json
uv run python -m tools.material_editor_roundtrip compare --manifest docs\phase37_material_editor_roundtrip_manifest.json --output docs\phase37_material_editor_roundtrip_compare_after_sandbox.json
```

New tests cover:

- fixture material generation
- Sandbox `/runpython` script generation
- launch command construction with `-project`
- before/after XML attribute comparison
- missing staged material detection
- Sandbox result-file detection
