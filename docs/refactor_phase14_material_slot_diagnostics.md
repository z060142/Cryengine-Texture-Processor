# Refactor Phase 14: Material Slot Diagnostics

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Turn the RC material-slot rules discovered in phases 10-13 into converter-side diagnostics.

The converter should not silently emit a request/MTL combination that is likely to make CGF geometry point at the wrong material. This phase adds an early warning layer while keeping the default RC request JSON schema unchanged.

## What Changed

- `model_processing.material_index_assigner` now attaches `diagnostics` to assigned material records.
- `output_formats.rc_request_builder.build_material_requests()` can include diagnostics when called with `include_diagnostics=True`.
- Default `build_import_request()` / `export_json()` output remains RC-only and does not include diagnostics.
- `tools.rc_smoke_test` now writes `preflight_material_diagnostics` into `<asset>.material_report.json`.

## Diagnostics Added

### Deleted Known FBX Slot

Code:

```text
deleted_known_fbx_slot_usage_unknown
```

Raised when:

```text
material is deleted
and material has a known FBX slot
and polygon usage is unknown or known used
```

Reason:

Phase 13 proved that `sub_index = -1` does not remove a geometry material id that is still used by the FBX. If polygon usage is unknown, deleting a known FBX slot is unsafe.

### Assigned Slot Differs From FBX Slot

Code:

```text
sub_index_differs_from_fbx_slot_usage_unknown
```

Raised when:

```text
material is not deleted
and assigned sub_index differs from known FBX slot
and polygon usage is unknown or known used
```

Reason:

Phases 10-12 proved that RC keeps CGF `MeshSubset.nMatID` aligned to raw FBX material slots. Moving a material to a different sub-index can make polygons point at the wrong `.mtl` slot.

## Deleted-Slot Report Evidence

The deleted-slot smoke report now includes:

```json
[
  {
    "severity": "hazard",
    "code": "deleted_known_fbx_slot_usage_unknown",
    "material": "Slot_1_Green",
    "fbx_slot": 1,
    "sub_index": -1,
    "source_order": 1,
    "assignment_reason": "deleted",
    "original_name": "Slot_1_Green"
  }
]
```

The post-RC verifier still sees:

```text
polygon 1 -> CGF MeshSubset.nMatID 1
request Slot_1_Green -> sub_index -1
MTL slot 1 -> unassigned
```

So the preflight hazard matches the actual RC output risk.

## Commands

Run the deleted-slot smoke probe:

```powershell
uv run python -m tools.rc_smoke_test --fbx "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_deleted\CE_MaterialSlotProbe_Deleted.fbx" --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled_deleted" --asset-name "CE_MaterialSlotProbe_Deleted" --materials "Slot_0_Red,Slot_1_Green:deleted,Slot_2_Blue"
```

Verify polygon material ids:

```powershell
uv run python -m tools.verify_controlled_fixture --manifest "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_deleted\CE_MaterialSlotProbe_Deleted.fixture_manifest.json" --report "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled_deleted\CE_MaterialSlotProbe_Deleted.material_report.json" --check-polygons
```

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_material_index_assigner.py tests\test_rc_request_builder.py tests\test_rc_smoke_test.py
uv run python -m tools.rc_smoke_test --fbx "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_deleted\CE_MaterialSlotProbe_Deleted.fbx" --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled_deleted" --asset-name "CE_MaterialSlotProbe_Deleted" --materials "Slot_0_Red,Slot_1_Green:deleted,Slot_2_Blue"
uv run python -m tools.verify_controlled_fixture --manifest "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_deleted\CE_MaterialSlotProbe_Deleted.fixture_manifest.json" --report "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled_deleted\CE_MaterialSlotProbe_Deleted.material_report.json" --check-polygons
```

## Remaining Work

- Done in phase 15: surface diagnostics in the PySide model import panel.
- Persist diagnostics alongside normal exports without adding non-RC fields to the RC request JSON.
- Extract true polygon material-slot usage from Blender/FBX, so hazards can be downgraded when a slot is proven unused.
