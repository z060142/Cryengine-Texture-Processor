# Refactor Phase 103: Direct RC Request and Scene Hierarchy

## Goal

Run the real FBX-to-CGF user flow for the car sample, then fix the first mismatch that blocked RC-compatible output.

This phase started by carrying Blender scene hierarchy into the generated import request. That worked, but it did not remove RC physicalization warnings. The real blocker was the JSON shape: RC expects the import request fields at the JSON root, not inside a `request` wrapper.

## Source Rule

`Code/Tools/RC/ResourceCompilerPC/FBX/ImportRequest.cpp` calls:

```cpp
ar(*this, "request", "Import request")
```

The `"request"` string is a yasli archive label. It does not mean the JSON file must contain:

```json
{"request": {...}}
```

CE editor ImportSettings chunks use direct root fields:

```json
{
  "source_filename": "asset.fbx",
  "output_ext": "cgf",
  "material_filename": "asset",
  "materials": []
}
```

When our exporter wrote `{"request": {...}}`, RC did not apply `material_filename`, `materials`, or `nodes`. The raw JSON still round-tripped into the CGF `ImportSettings` chunk, so report-side ImportSettings comparisons looked good while the compiled CGF used RC defaults.

## Evidence

Broken wrapper output, before this phase:

- Generated JSON root: `request`
- CGF material name: `default`
- CGF material physicalize types: all `4096`
- `4096` is `PHYS_GEOM_TYPE_DEFAULT`
- MeshPhysicsData chunks: `21`
- Physicalizer warnings were emitted

Fixed direct-root output:

- Generated JSON root: direct import fields
- CGF material name: `kb3d_citycarsessentialssedan-native`
- CGF material physicalize types: all `-1`
- `-1` is `PHYS_GEOM_TYPE_NONE`
- MeshPhysicsData chunks: `0`
- Physicalizer warnings disappeared

Direct comparison against the original car CGF:

```text
generated direct request:
  chunk_count: 173
  meshphysics_count: 0
  physicalize_types: [-1 x16]
  sub_material_count: 16

original car CGF:
  chunk_count: 173
  meshphysics_count: 0
  physicalize_types: [-1 x16]
  sub_material_count: 16
```

## Implemented

- `output_formats/json_exporter.py`
  - Default export is now direct-root JSON.
  - Legacy wrappers remain possible for report fixtures by passing `wrapper_name`.

- `tools/blender_material_inspector.py`
  - Writes `scene_hierarchy` into the FBX material manifest.
  - Scene nodes include `mass: -1.0` and `density: -1.0`, matching CE editor-style node metadata.

- `tools/rc_smoke_test.py`
  - Pulls `scene_hierarchy` from the material manifest into generated RC requests.

- `output_formats/rc_request_builder.py`
  - Preserves RC-supported source-backed node fields such as `mass`, `density`, and `no_hit_refinement`.

- `output_formats/rc_import_schema.py`
  - Corrected the schema note: RC reads a direct root object; `request` is an archive label.

## Verified

Targeted tests:

```text
uv run python -m pytest tests\test_rc_request_builder.py tests\test_rc_smoke_test.py tests\test_rc_import_runner.py tests\test_blender_material_inspector.py tests\test_material_manifest.py tests\test_rc_request_builder.py
90 passed
```

Real car user flow:

```text
uv run python -m tools.blender_material_inspector --fbx S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase103_direct_request\kb3d_citycarsessentialssedan-native.fbx
uv run python -m tools.rc_smoke_test --rc S:\Crytek\crytek\cryengine-57-lts\5.7.1\Tools\rc\rc.exe --fbx S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase103_direct_request\kb3d_citycarsessentialssedan-native.fbx --work-dir S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase103_direct_request\rc_work --asset-name kb3d_citycarsessentialssedan-native --materials-from-manifest
```

Output evidence:

```text
S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase103_direct_request\rc_work\kb3d_citycarsessentialssedan-native.cgf
```

## Rule for Plugin/Tool Authors

For FBX-to-CGF import request JSON:

1. Write import fields at the JSON root.
2. Use `materials[].physicalize: "no"` for render-only materials.
3. Use stable `materials[].sub_index` values for final CGF material ids.
4. Do not trust the `ImportSettings` chunk alone as proof that RC used the settings; verify the compiled `MtlName` physicalize types and the absence/presence of `MeshPhysicsData`.

