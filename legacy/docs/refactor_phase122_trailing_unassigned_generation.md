# Phase 122 - Generated Trailing Unassigned Material Slot

## Goal

Treat CryEngine's trailing `<unassigned>` material slot as an expected model
conversion condition, not as an accidental cleanup artifact.

The real car sample has:

```text
request / ImportSettings materials: 17
MTL sub-material slots: 17
CGF used material ids: 0..15
slot 16: <unassigned>
```

The converter previously generated only the 16 real material slots for this
sample. That still produced a valid CGF, but it did not match the CE-side asset
shape that tools and diagnostics must assume exists.

## Rule

For user-facing model export and RC smoke flows:

```text
append one trailing <unassigned> request/MTL slot after the highest used material slot
```

The placeholder is valid only when:

```text
slot > max(CGF material id)
```

It is a hazard only when CGF geometry actually uses that material id.

## Implementation

- `model_processing.material_slot_table`
  - adds `TRAILING_UNASSIGNED_MATERIAL_NAME`
  - adds `append_trailing_unassigned_slot()`
  - keeps gap placeholders as `unassigned`
  - uses `<unassigned>` only for the CE-style trailing placeholder
  - does not append if the next slot would exceed RC's `MAX_SUB_MATERIALS`

- `output_formats.mtl_exporter`
  - accepts `include_trailing_unassigned`

- `output_formats.rc_request_builder`
  - accepts `include_trailing_unassigned`

- `output_formats.json_exporter`
  - passes `include_trailing_unassigned` through to the request builder

- user-flow callers now enable the option:
  - PySide/main model MTL export
  - PySide/main FBX/JSON/optional RC export
  - `tools.rc_smoke_test`

General builders keep the default off so narrow schema/unit tests can still
describe the minimal request shape explicitly.

## Real Car Verification

Input:

```text
S:\Crytek\crytek\Stripped to the bone\example\car\kb3d_citycarsessentialssedan-native.fbx
```

Commands:

```powershell
uv run python -m tools.blender_material_inspector --fbx "S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase122_trailing_unassigned\kb3d_citycarsessentialssedan-native.fbx"
uv run python -m tools.rc_smoke_test --rc "S:\Crytek\crytek\cryengine-57-lts\5.7.1\Tools\rc\rc.exe" --fbx "S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase122_trailing_unassigned\kb3d_citycarsessentialssedan-native.fbx" --work-dir "S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase122_trailing_unassigned\rc_work" --asset-name kb3d_citycarsessentialssedan-native --materials-from-manifest
```

Report:

```text
S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase122_trailing_unassigned\rc_work\kb3d_citycarsessentialssedan-native.material_report.json
```

Observed:

```json
{
  "request_material_count": 17,
  "mtl_slot_count": 17,
  "cgf_material_id_count": 16,
  "unassigned_slot_counts": {
    "trailing_unassigned_placeholder": 1
  },
  "used_unassigned_material_count": 0,
  "unassigned_slots_ok": true,
  "action_required": false
}
```

The generated request and MTL both end with:

```json
{
  "name": "<unassigned>",
  "physicalize": "no",
  "sub_index": 16
}
```

The generated CGF still uses only material ids `0..15`.

## Verification

- `uv run python -m pytest tests/test_material_slot_table.py tests/test_mtl_exporter.py tests/test_rc_request_builder.py tests/test_rc_smoke_test.py tests/test_material_mapping_report.py tests/test_pyside_model_import_diagnostics.py`
- `uv run python -m compileall main.py model_processing output_formats tools tests`
- `uv run python -m pytest`
- `uv run python tools/converter_schema.py --check docs/converter_schema.json`
- `uv lock --check`
- `git diff --check`
