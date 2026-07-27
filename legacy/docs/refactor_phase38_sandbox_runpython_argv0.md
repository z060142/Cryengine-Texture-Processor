# Refactor Phase 38: Sandbox `/runpython` Argv0 Workaround

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Find why the Phase 37 Material Editor round-trip harness did not produce a Sandbox result file, and make the automated launch match Sandbox's real `/runpython` parser.

## Source Evidence

Sandbox command-line parsing lives in:

```text
Code/Sandbox/EditorQt/CryEdit.cpp
```

The parser calls `CommandLineToArgvW(GetCommandLineW(), &argc)` and then walks every token from index `0`.

Relevant behavior:

```text
first non-flag token -> m_strFileName
later non-flag tokens -> m_file
/runpython -> m_bRunPythonScript = true
```

Later startup runs:

```text
general.run_file '<m_strFileName>'
```

That means a normal command such as:

```powershell
Sandbox.exe -project <project.cryproject> /BatchMode /runpython <script.py>
```

can make Sandbox treat `Sandbox.exe` itself as `m_strFileName`, because `argv[0]` is included in the parser loop.

## What Changed

`tools/material_editor_roundtrip.py` now writes a separate `sandbox_popen` block into the manifest:

```json
{
  "executable": "S:\\Crytek\\crytek\\cryengine-57-lts\\5.7.1\\bin\\win_x64\\Sandbox.exe",
  "args": [
    "S:\\Crytek\\crytek\\Stripped to the bone\\material_editor_roundtrip_phase37\\run_material_roundtrip.py",
    "-project",
    "S:\\Crytek\\crytek\\cryengine-gamesdk-sample-project\\5.7.1\\gamesdk.cryproject",
    "/BatchMode",
    "/runpython"
  ],
  "strategy": "script_path_as_argv0"
}
```

The run command uses:

```text
subprocess.Popen(args, executable=Sandbox.exe)
```

This lets Windows execute `Sandbox.exe` while the command line starts with the Python script path. The human-readable `launch_command` is still kept in the manifest, but automated runs should use `sandbox_popen`.

Run reports now also record:

```text
executable
launch_strategy
```

## Generated Artifacts

Updated manifest:

```text
docs/phase37_material_editor_roundtrip_manifest.json
```

Argv0 run report:

```text
docs/phase38_material_editor_roundtrip_sandbox_run_argv0.json
```

Post-argv0 compare:

```text
docs/phase38_material_editor_roundtrip_compare_after_argv0.json
```

## Result

The editor log confirms the workaround took effect:

```text
Command Line: "S:\Crytek\crytek\Stripped to the bone\material_editor_roundtrip_phase37\run_material_roundtrip.py" -project S:\Crytek\crytek\cryengine-gamesdk-sample-project\5.7.1\gamesdk.cryproject /BatchMode /runpython
Executable: S:\Crytek\crytek\cryengine-57-lts\5.7.1\bin\win_x64\Sandbox.exe
```

The run still did not complete:

```json
{
  "state": "timeout",
  "returncode": 1,
  "result_exists": false
}
```

The post-run compare still has no material changes:

```json
{
  "case_count": 6,
  "changed_count": 0,
  "unchanged_count": 6,
  "missing_after_count": 0,
  "sandbox_result_present": false
}
```

Interpretation:

```text
The argv0 parser trap is now ruled out.
This is still not evidence that the Material Editor preserves or rewrites GenMask/StringGenMask.
Sandbox reaches only early initialization in editor.log before the timeout.
```

Phase 39 narrowed this further: `/BatchMode` itself stalls during early system config in this local Sandbox build, while a normal Editor `-edCommand` launch reaches GameSDK initialization but blocks at `WaitForAllowSendClientConnect`.

No `Sandbox.exe` process remained after the timeout.

## Rule

For automated Material Editor `/runpython` experiments, use `sandbox_popen`, not `launch_command`.

Treat a Material Editor round-trip as successful only when:

```text
state = result
result_exists = true
sandbox_result.results[*].success = true
```

Until then, the Phase 35/36 exporter mask policy remains evidence-limited.

## Next Work

- Discover why Sandbox stalls early after the corrected argv0 launch.
- Try a visible interactive Sandbox run with the same generated script.
- Check whether this Sandbox build requires a later Editor init hook instead of immediate `/runpython`.
- If `/runpython` remains unreliable, add a tiny Editor-side command/plugin or direct C++ harness that loads, updates, and saves `.mtl` files.

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_material_editor_roundtrip.py
uv run python -m tools.material_editor_roundtrip prepare --work-dir "S:\Crytek\crytek\Stripped to the bone\material_editor_roundtrip_phase37" --output docs\phase37_material_editor_roundtrip_manifest.json
uv run python -m tools.material_editor_roundtrip compare --manifest docs\phase37_material_editor_roundtrip_manifest.json --output docs\phase37_material_editor_roundtrip_compare_initial.json
uv run python -m tools.material_editor_roundtrip run --manifest docs\phase37_material_editor_roundtrip_manifest.json --timeout 180 --output docs\phase38_material_editor_roundtrip_sandbox_run_argv0.json
uv run python -m tools.material_editor_roundtrip compare --manifest docs\phase37_material_editor_roundtrip_manifest.json --output docs\phase38_material_editor_roundtrip_compare_after_argv0.json
```
