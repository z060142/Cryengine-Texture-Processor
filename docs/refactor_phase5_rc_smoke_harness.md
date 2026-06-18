# Refactor Phase 5: RC Smoke Test Harness

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Create a repeatable smoke-test path for the real Resource Compiler conversion step:

```text
sample.fbx + generated .mtl + generated request JSON -> rc.exe -> .cgf
```

This phase does not claim a successful real asset conversion yet. It adds the tool that will run it and records the current blocker: there is an RC executable available, but no clean sample FBX asset in the checked locations.

## What Changed

- Added `tools/rc_smoke_test.py`.
- Added `tools/__init__.py` so the smoke tool can be run as a module.
- Added `tests/test_rc_smoke_test.py`.

The smoke tool:

1. takes a source FBX
2. creates a working directory
3. copies the FBX as `<asset>.fbx`
4. writes `<asset>.mtl`
5. writes `<asset>.json` with a `request` root
6. runs `RCImportRunner`
7. reports paths, expected output, stdout/stderr, and error

## Usage

```powershell
python -m tools.rc_smoke_test `
  --rc "S:\Crytek\crytek\cryengine-57-lts\5.7.1\Tools\rc\rc.exe" `
  --fbx "S:\path\to\sample.fbx" `
  --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work" `
  --asset-name "smoke_asset" `
  --materials "Default"
```

If `--asset-name` is omitted, the source FBX basename is used. If `--materials` is omitted, the generated MTL/request use one material named `Default`.

## Local Discovery

Found RC executable:

```text
S:\Crytek\crytek\cryengine-57-lts\5.7.1\Tools\rc\rc.exe
```

No clean sample model asset was found in:

```text
S:\Crytek\crytek\Stripped to the bone\Cryengine-Texture-Processor
S:\Crytek\crytek\CRYENGINE_Source-release
```

The only `.obj` hits under the converter tree were PySide build artifacts inside `.venv`, not model assets.

## Attempted Smoke Command

Command:

```powershell
python -m tools.rc_smoke_test --rc "S:\Crytek\crytek\cryengine-57-lts\5.7.1\Tools\rc\rc.exe" --fbx "S:\Crytek\crytek\Stripped to the bone\missing_sample.fbx" --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work"
```

Result:

```text
success: False
error: Source FBX not found: S:\Crytek\crytek\Stripped to the bone\missing_sample.fbx
```

This is the desired failure mode for missing fixtures: the tool does not crash and does not pretend conversion succeeded.

## Tests Added

`tests/test_rc_smoke_test.py` covers:

- material name CLI parsing
- smoke model data creation with empty node list
- FBX copy plus MTL/request generation
- missing RC path
- missing source FBX
- fake runner success path

## Verification

Passed:

```powershell
python -m pytest tests
python -m compileall tools tests
```

## Next Step

Provide or generate a small valid FBX fixture, then run:

```powershell
python -m tools.rc_smoke_test --rc "<rc.exe>" --fbx "<sample.fbx>" --work-dir "<work-dir>"
```

After that, inspect:

- generated request JSON
- generated MTL
- RC stdout/stderr
- expected `.cgf`
- material slot alignment in the resulting asset
