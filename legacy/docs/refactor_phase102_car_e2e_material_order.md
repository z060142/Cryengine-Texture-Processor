# Phase 102 - Car E2E Material Order Flow

## Goal

Run the user-facing FBX-to-CGF path before adding more narrow proofs:

```powershell
uv run python -m tools.blender_material_inspector --fbx <car.fbx>
uv run python -m tools.rc_smoke_test --rc <rc.exe> --fbx <car.fbx> --work-dir <work> --asset-name <asset> --materials-from-manifest
```

Sample:

```text
S:\Crytek\crytek\Stripped to the bone\example\car\kb3d_citycarsessentialssedan-native.fbx
```

## E2E Finding

The old Blender inspector material table used Blender object-slot first-seen order.
That order is not the same as the material table RC writes into the CGF for this
real car sample.

Old generated order:

```text
0 KB3D_CEV_UndercarriageTrim
1 KB3D_CEV_SeatsDriverATrim
2 KB3D_CEV_RubberTrim
3 KB3D_CEV_PlasticTileableA
...
14 KB3D_CEV_TiresSedans
15 KB3D_CEV_WheelRimsA
```

RC/CGF order:

```text
0 KB3D_CEV_UndercarriageTrim
1 KB3D_CEV_SeatsDriverATrim
2 KB3D_CEV_TiresSedans
3 KB3D_CEV_WheelRimsA
4 KB3D_CEV_RubberTrim
...
```

Raw FBX string first occurrence matched the RC/CGF order for this sample, while
Blender's imported object-slot order did not.

## Changes

`tools.blender_material_inspector` now:

- still uses Blender to inspect mesh polygons and material usage
- orders the manifest material table by first occurrence of each material name in the raw FBX file
- records `fbx_first_offset` and `slot_source`
- marks generated generic manifests with `polygon_verification: material_table_only`
- writes generic material rows with explicit `physicalize: "no"`

`tools.material_mapping_report` now:

- parses CGF embedded ImportSettings when RC stores a `request` wrapper
- treats `polygon_verification: material_table_only` as a material-table semantic check, not a polygon-center subset check
- can build reports from existing `.cgf/.mtl` bundles through `build_existing_output_material_report()`

New CLI:

```powershell
uv run python -m tools.existing_material_bundle_report <asset.cgf> --mtl <asset.mtl>
```

This is for user-provided examples that already have RC output and may not have
the original request JSON beside them.

Real CLI check against the final E2E output:

```json
{
  "request_source": {
    "type": "cgf_import_settings",
    "error": "",
    "import_settings_meta": {
      "chunk_id": 194,
      "version": 0,
      "material_count": 16
    }
  },
  "alignment_ok": true,
  "cgf_import_settings_alignment_ok": true,
  "cgf_material_id_alignment_ok": true
}
```

## Final E2E Result

Final work dir:

```text
S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase102_final\rc_work
```

Report summary:

```json
{
  "alignment_ok": true,
  "cgf_import_settings_alignment_ok": true,
  "import_settings_material_count": 16,
  "cgf_material_id_alignment_ok": true,
  "fixture_semantic_ok": true,
  "polygon_checks_skipped": true,
  "polygon_count": 111972,
  "request_physicalize_values": ["no"],
  "nodes_count": 0
}
```

The material table now matches the CGF `MtlName` order:

```text
0 KB3D_CEV_UndercarriageTrim
1 KB3D_CEV_SeatsDriverATrim
2 KB3D_CEV_TiresSedans
3 KB3D_CEV_WheelRimsA
4 KB3D_CEV_RubberTrim
5 KB3D_CEV_PlasticTileableA
6 KB3D_CEV_PlasticTrimA
7 KB3D_CEV_SedanExteriorBody
```

## Remaining Flow Gap

RC still logged physicalized render geometry warnings even after request materials
used `physicalize: "no"`.

The final generated request has:

```json
{
  "request_physicalize_values": ["no"],
  "nodes_count": 0
}
```

This suggests the next E2E issue is not the material rows, but the empty request
`nodes` emitted by the current smoke/model path. The real car CGF ImportSettings
contains the source node hierarchy with `mass: -1.0` and `density: -1.0`; the
converter's user flow should preserve or reconstruct that node hierarchy before
claiming fully correct arbitrary FBX conversion.

## Verification

```powershell
uv run python -m pytest tests\test_blender_material_inspector.py tests\test_material_mapping_report.py tests\test_rc_request_builder.py tests\test_material_manifest.py tests\test_rc_smoke_test.py
```

Result:

```text
111 passed
```
