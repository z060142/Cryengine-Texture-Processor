# Refactor Phase 6: Real RC Smoke Success

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Run the conversion pipeline against a real `rc.exe` and a real FBX sample instead of only testing the harness with fake runners.

## What Changed

- `tools/rc_smoke_test.py` can now discover a default FBX fixture.
- Added known local GameSDK sample candidates:

```text
S:\Crytek\crytek\cryengine-gamesdk-sample-project\5.7.1\gamesdk\objects\cubao\CubeA.fbx
S:\Crytek\crytek\cryengine-gamesdk-sample-project\5.7.1\gamesdk\objects\cubez\CubeA.fbx
```

- `--fbx` is now optional when one of those samples exists.
- `tests/test_rc_smoke_test.py` covers default FBX discovery.

## Successful Smoke Command

Command:

```powershell
uv run python -m tools.rc_smoke_test --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_default" --asset-name "CubeA_default_smoke" --materials "Default"
```

Discovered RC:

```text
S:\Crytek\crytek\cryengine-57-lts\5.7.1\Tools\rc\rc.exe
```

Discovered FBX:

```text
S:\Crytek\crytek\cryengine-gamesdk-sample-project\5.7.1\gamesdk\objects\cubao\CubeA.fbx
```

Generated bundle:

```text
S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_default\CubeA_default_smoke.fbx
S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_default\CubeA_default_smoke.mtl
S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_default\CubeA_default_smoke.mtl.cryasset
S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_default\CubeA_default_smoke.json
```

RC output:

```text
S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_default\CubeA_default_smoke.cgf
S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_default\CubeA_default_smoke.cgf.cryasset
```

The generated `.cgf` was present and non-empty.

## Request JSON Used

```json
{
  "request": {
    "source_filename": "CubeA_default_smoke.fbx",
    "output_ext": "cgf",
    "material_filename": "CubeA_default_smoke",
    "unit_size": "cm",
    "scale": 1.0,
    "forward_up_axes": "-Y+Z",
    "merge_all_nodes": false,
    "scene_origin": false,
    "ignore_custom_normals": false,
    "ignore_uv": false,
    "materials": [
      {
        "name": "Default",
        "physicalize": "no_collide",
        "sub_index": 0
      }
    ],
    "nodes": [],
    "jointPhysicsData": [],
    "autolodsettings": {
      "GenerateAutomaticLODs": false
    }
  }
}
```

The smoke request intentionally uses an empty node list. RC accepted the request and imported the full sample scene.

## RC Evidence

RC log included:

```text
Registered FbxConverter ("fbx")
Importing scene from file '...\CubeA_default_smoke.fbx' to '...\CubeA_default_smoke.cgf'
FBX unit: centimeter, 1 cm
Converting scene's forward & up coordinate axes '+Z+Y' to CryEngine's '-Y+Z'
Final scale (includes user scale and conversion to meters): 0.010000
```

This proves the runner is reaching the real FBX converter path, not merely invoking RC on an unrelated file type.

## Verification

Passed:

```powershell
uv run python -m pytest tests
uv run python -m tools.rc_smoke_test --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_default" --asset-name "CubeA_default_smoke" --materials "Default"
```

## Remaining Work

- Inspect the generated `.cgf` material table with a CryEngine-aware reader or editor.
- Run smoke with more than one material to verify sub-index alignment survives RC import.
- Add optional smoke output assertions to CI-like tests only when local RC and sample assets are present.
- Feed Blender-exported FBX through the same harness, not only GameSDK FBX.
