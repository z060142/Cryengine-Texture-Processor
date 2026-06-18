# Refactor Phase 39: Sandbox Batch Mode and `edCommand` Probe

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Find the remaining blocker after Phase 38 proved the `/runpython` argv0 workaround.

The question was whether Sandbox failed because of the argv0 strategy, because `/BatchMode` is broken in this local build, or because the generated Material Editor script itself is wrong.

## Source Evidence

`/BatchMode` parsing:

```text
Code/Sandbox/EditorQt/CryEdit.cpp
```

Relevant behavior:

```text
/BatchMode -> m_bConsoleMode = true
```

`edCommand` execution:

```text
Code/Sandbox/EditorQt/CryEdit.cpp
```

Relevant behavior:

```text
FindArg(eCLAT_Pre, "edCommand")
GetIEditorImpl()->ExecuteCommand(pCommandArg->GetValue())
```

`WaitForAllowSendClientConnect` source:

```text
Code/CryEngine/CryAction/Network/GameContext.cpp
```

Relevant behavior:

```text
if (gEnv->IsEditor())
    AddWaitValue(..., &m_bAllowSendClientConnect, true, "WaitForAllowSendClientConnect", 20.0f)
```

The value is set by:

```text
Code/CryEngine/CryAction/ActionGame.cpp
CActionGame::BlockingSpawnPlayer()
m_pGameContext->AllowCallOnClientConnect()
```

## What Changed

`tools/material_editor_roundtrip.py` now records a second automated launch option:

```json
{
  "strategy": "normal_editor_edCommand_run_file",
  "args": [
    "Sandbox.exe",
    "-project",
    "gamesdk.cryproject",
    "-edCommand",
    "general.run_file '<script.py>'"
  ]
}
```

The run command now accepts:

```powershell
uv run python -m tools.material_editor_roundtrip run --manifest docs\phase37_material_editor_roundtrip_manifest.json --strategy argv0
uv run python -m tools.material_editor_roundtrip run --manifest docs\phase37_material_editor_roundtrip_manifest.json --strategy edcommand
uv run python -m tools.material_editor_roundtrip run --manifest docs\phase37_material_editor_roundtrip_manifest.json --strategy launch_command
```

Default remains `argv0`, which preserves the Phase 38 behavior.

## Probe Results

Baseline normal launch:

```text
docs/phase39_sandbox_baseline_launch_probe.json
```

Result:

```json
{
  "state": "timeout",
  "returncode": 1
}
```

Interpretation:

```text
Timeout is expected for a normal Editor launch because Sandbox stays open.
The important signal is editor.log: it advanced into project loading, renderer setup, shader cache work, AI monitor startup, and animation tasks.
```

Batch mode only:

```text
docs/phase39_sandbox_batchmode_launch_probe.json
```

Result:

```json
{
  "state": "timeout",
  "returncode": 1
}
```

Editor log stopped at 29 lines, immediately after early config output:

```text
Command Line: ... Sandbox.exe -project ... /BatchMode
Loading Config file %ENGINEROOT%/system.cfg
con_debug=0
```

Interpretation:

```text
On this local Sandbox build/environment, /BatchMode does not progress far enough to initialize the Editor.
This explains why Phase 37 and Phase 38 never reached Python.
```

Normal Editor plus `-edCommand`:

```text
docs/phase39_material_editor_roundtrip_sandbox_run_edcommand_no_batch_probe.json
```

Result:

```json
{
  "state": "timeout",
  "result_exists": false
}
```

Editor log progressed into GameSDK initialization but then repeated:

```text
Waiting for value WaitForAllowSendClientConnect
```

Interpretation:

```text
Removing /BatchMode lets Sandbox initialize much further, but the GameSDK editor startup blocks in CryAction game context before edCommand reaches the generated Python script.
```

Post-probe compare:

```text
docs/phase39_material_editor_roundtrip_compare_after_edcommand_no_batch.json
```

Summary:

```json
{
  "case_count": 6,
  "changed_count": 0,
  "unchanged_count": 6,
  "missing_after_count": 0,
  "sandbox_result_present": false
}
```

## Rule

Do not interpret unchanged `.mtl` files from these probes as Material Editor preservation behavior.

The generated Material Editor script has not successfully run yet.

Known launch behavior:

```text
/BatchMode + /runpython      -> stalls during early system config
/BatchMode + -edCommand      -> stalls during early system config
normal Editor + -edCommand   -> reaches GameSDK init, then waits for WaitForAllowSendClientConnect
normal Editor only           -> reaches deep startup/shader work
```

## Next Work

- Try a lighter project that does not start the GameSDK game context.
- Try disabling GameSDK startup/game context from command line or project config if a documented cvar path exists.
- If the Editor must be driven through GameSDK, run a visible interactive launch and resolve the game-context wait manually once to see whether `edCommand` fires afterward.
- If Sandbox automation remains blocked, build a tiny Editor-side command/plugin or C++ harness that loads and saves `.mtl` through `CMaterialManager` directly.

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_material_editor_roundtrip.py
uv run python -m tools.material_editor_roundtrip prepare --work-dir "S:\Crytek\crytek\Stripped to the bone\material_editor_roundtrip_phase37" --output docs\phase37_material_editor_roundtrip_manifest.json
uv run python -m tools.material_editor_roundtrip compare --manifest docs\phase37_material_editor_roundtrip_manifest.json --output docs\phase39_material_editor_roundtrip_compare_after_edcommand_no_batch.json
```
