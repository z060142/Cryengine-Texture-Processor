# Refactor Phase 4: RC Import Runner

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Move RC execution out of ad-hoc UI/background-thread code into a small, testable service. This is the next step toward real end-to-end conversion: FBX + MTL + request JSON -> `rc.exe` -> `.cgf` or other CryEngine model output.

## What Changed

- Added `utils/rc_import_runner.py`.
- `main.py` now uses `RCImportRunner` after JSON export instead of starting the old `RCProcessor` background thread.
- The runner returns an `RCImportResult` object with:
  - success flag
  - command arguments
  - request JSON path
  - expected output path
  - return code
  - stdout
  - stderr
  - error message

The old `utils/rc_processor.py` and `utils/cgf_processor.py` are still present for compatibility, but the model export path now uses the new runner.

## Command Shape

The runner builds:

```text
rc.exe request.json /overwriteextension=fbx /overwritesourcefile=asset.fbx /overwritefilename=asset.cgf
```

Notes:

- `/overwriteextension=fbx` follows the CryEngine editor route so RC sends the JSON request through the FBX converter.
- `/overwritesourcefile` is optional because the JSON request already contains `source_filename`, but the model export path passes it explicitly as a stronger guard.
- Arguments are passed as a list to `subprocess.run()`. The command builder does not embed extra quote characters in individual arguments.

## Output Detection

The runner parses the request JSON and derives the expected output from:

```text
request.output_ext
```

Example:

```text
chair.json + output_ext cgf  -> chair.cgf
walk.json  + output_ext caf  -> walk.caf
body.json  + output_ext skin -> body.skin
```

RC execution is considered successful only when:

1. RC returns exit code `0`.
2. The expected output file exists.

This catches a common failure mode where RC exits cleanly enough for the process but does not produce the model file.

## Tests Added

`tests/test_rc_import_runner.py` covers:

- command assembly without embedded quote characters
- output extension parsing from request JSON
- missing RC path
- missing JSON
- successful RC process with generated output
- RC exit code failure
- RC return code `0` but missing output file

## Verification

Passed:

```powershell
python -m pytest tests
python -m compileall main.py utils tests
```

## Remaining Work

- Run against the real `Tools/rc/rc.exe` from the CryEngine source tree.
- Add UI feedback for `RCImportResult.stdout`, `stderr`, and `error`.
- Add a small fixture asset pipeline for real smoke tests.
- Decide whether RC execution should be sync in a worker thread or queued as a task in the PySide UI.
- Retire or adapt the older `RCProcessor` and `CGFProcessor` once the new runner covers all call sites.
