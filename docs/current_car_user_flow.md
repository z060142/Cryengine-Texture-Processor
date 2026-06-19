# Current Car User Flow

This is the current coarse regression path for the model/material converter.
It replaces the earlier habit of splitting every observation into another
numbered phase.

## Scope Boundary

The first working slice is limited to:

- raw texture outputs are accepted by the RC texture gate
- FBX import request JSON maps source material names to final CE slots
- generated MTL slot order matches the request `sub_index` table
- RC.exe produces a CGF whose mesh subset material ids align with the MTL slots
- material state can be copied from a CE-authored reference MTL and compared
- `<unassigned>` is treated as expected CE behavior unless a mesh subset uses it

Do not expand this slice into material editing UI, Blender plugin UX, new shader
authoring, or broad engine reverse engineering. Those belong to later work once
this regression path stays stable.

## Current Evidence Run

Command:

```powershell
uv run python -m tools.rc_smoke_test --rc "S:\Crytek\crytek\cryengine-57-lts\5.7.1\Tools\rc\rc.exe" --fbx "S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase127_material_overrides\kb3d_citycarsessentialssedan-native.fbx" --work-dir "S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_current\rc_work" --asset-name kb3d_citycarsessentialssedan-native --materials-from-manifest --material-overrides docs\car_native_material_overrides.json --reference-mtl "S:\Crytek\crytek\Stripped to the bone\example\car\kb3d_citycarsessentialssedan-native.mtl" --material-state-compare-output docs\current_car_user_flow_material_state_compare.json --mtl-schema-gate-output docs\current_car_user_flow_mtl_schema_gate.json --texture-output-dir "S:\Crytek\crytek\Stripped to the bone\example\car" --texture-output-format "dds,tif" --texture-output-gate-output docs\current_car_user_flow_texture_output_gate.json
```

Result:

- RC result: `success: True`
- output CGF: `S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_current\rc_work\kb3d_citycarsessentialssedan-native.cgf`
- material report: `S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_current\rc_work\kb3d_citycarsessentialssedan-native.material_report.json`
- material state compare: `ok: True`
- MTL schema gate: `ok: True`, `material_count: 18`, `diagnostic_count: 0`
- texture output gate: `ok: True`, `group_count: 17`, `output_count: 73`, `diagnostic_count: 0`
- slot alignment: `slot_alignment_ok: True`
- CGF material id alignment: `cgf_material_id_alignment_ok: True`
- CGF import settings alignment: `cgf_import_settings_alignment_ok: True`
- fixture semantic alignment: `fixture_material_semantic_alignment_ok: True`
- `<unassigned>` state: one trailing placeholder, `used_unassigned_material_count: 0`

## Rules Fixed By This Run

### Texture outputs

CE treats `.tif` and `.dds` texture outputs as the same practical asset identity
for this converter path. The gate accepts both as RC source formats and groups
files by base name plus CE suffix, not by extension. If both
`wall_diff.dds` and `wall_diff.tif` exist, they represent the same `diff`
texture output for gate purposes.

The output keys currently used by the gate are:

```text
diff      -> Diffuse
spec      -> Specular
ddna/ddn  -> Bumpmap
displ     -> Heightmap
emissive  -> Emittance
sss       -> SubSurface
roughness -> Opacity, observed car compatibility alias
opacity   -> Opacity
```

### Material slots

The RC request row:

```json
{
  "name": "KB3D_CEV_SedanExteriorBody",
  "physicalize": "no",
  "sub_index": 7
}
```

means:

```text
FBX material name
-> request.materials[].name
-> request.materials[].sub_index
-> generated MTL SubMaterials child order
-> RC CGF mesh subset material_id
```

For this car sample, RC generated 16 used material ids from request slots
`0..15`; slot `16` is the trailing `<unassigned>` placeholder and is not used by
any CGF mesh subset.

### Material state

The converter should prefer CE-authored MTL state when available:

```text
reference .mtl
-> tools.mtl_override_extractor
-> docs/car_native_material_overrides.json
-> generated MTL
-> tools.mtl_material_state_compare
```

This current run compares equal for high-value state by material name:

```text
Shader, MtlFlags, GenMask, StringGenMask, PublicParams
```

## Missing Pieces After This Slice

The remaining material work should stay bounded to these items:

- define the fallback material state when no CE-authored MTL exists
- document which `PublicParams` and shader masks are evidence-backed versus
  compatibility-preserved
- expose material id/slot diagnostics in the PySide workflow, not only CLI JSON
- decide how a Blender plugin supplies or edits `sub_index` and material names
- keep `<unassigned>` visible as a normal placeholder, while blocking the case
  where a real mesh subset uses it

Anything outside that list should require a new explicit decision before it is
added to this first working slice.

## Verification Files

- `docs/current_car_user_flow_material_state_compare.json`
- `docs/current_car_user_flow_mtl_schema_gate.json`
- `docs/current_car_user_flow_texture_output_gate.json`
- `docs/converter_contract.md`
- `docs/converter_schema.json`
