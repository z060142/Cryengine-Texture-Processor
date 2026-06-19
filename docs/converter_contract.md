# Converter Contract

This document is the compact contract for external tools such as a custom FBX
converter or Blender plugin. It points to the machine-readable snapshot in
`docs/converter_schema.json` and avoids requiring another pass through the full
CryEngine source tree.

## Material Slot Contract

For RC FBX import requests, each `request.materials[]` row must provide:

```json
{
  "name": "Body",
  "physicalize": "no",
  "sub_index": 0
}
```

Meaning:

- `name` is the source FBX scene material name that RC matches by name.
- `physicalize` is one of `no`, `default`, `obstruct`, `no_collide`, or
  `proxy_only`.
- `sub_index` is the final CryEngine sub-material id. Non-negative values map
  to the generated MTL slot and the CGF mesh subset material id.

Evidence-backed identity chain:

```text
FBX material name
-> request.materials[].name
-> request.materials[].sub_index
-> MTL SubMaterials child order
-> CGF MeshSubset material_id
```

Known FBX material ids are one-based. When the raw FBX id is available, the raw
zero-based FBX slot is `fbx_material_id - 1`.

## Assignment Priority

When the converter assigns slots itself, use this priority:

1. Explicit `sub_index` when `auto_assigned` or `ui_autoflag` is false.
2. Known FBX material id, mapped to `fbx_material_id - 1`, if that slot is free.
3. Existing MTL child order by matching material name, if that slot is free.
4. First free slot.

The supported final slot range is `0..127`. `sub_index = -1` means deleted.
Values `>= 128` are normalized by RC to `-1`, which can delete matching faces.

## Unassigned Slots

Treat unassigned slots as normal CryEngine behavior, not as a removable bug.

- Intermediate gaps are emitted as `unassigned` placeholders in the expanded MTL
  slot table.
- A trailing `<unassigned>` placeholder can exist in request/MTL and be absent
  from the CGF `MtlName` table when no mesh subset uses it.
- A used `<unassigned>` material is still a hazard and must be surfaced by the
  material report.

## Gate Hazards

External tools should block or warn on these conditions before calling RC:

- duplicate non-negative `sub_index` values
- `sub_index >= 128`
- material names that differ only by case
- deleting a known FBX slot unless polygon usage proves it is unused
- omitting source materials from a non-empty request material list
- CGF material ids that are absent from the request table or generated MTL slot
  table after an RC smoke run

The authoritative machine-readable version is:

```text
docs/converter_schema.json -> material_slot_mapping.assignment_policy
```

## Material State Contract

For high-value material state, prefer an existing CryEngine-authored `.mtl` over
exporter guesses.

Authoritative path:

```text
reference .mtl
-> tools.mtl_override_extractor
-> cryengine_material_overrides.v1
-> material_overrides[MaterialName].cryengine_material
-> generated MTL
-> tools.mtl_material_state_compare
```

The override may provide:

- material attributes such as `Shader`, `MtlFlags`, `Diffuse`, `Specular`,
  `Opacity`, `Shininess`, `AlphaTest`, and shader-specific attrs
- `GenMask` and `StringGenMask`
- `PublicParams`

When a reference MTL exists, `tools.mtl_material_state_compare` is the gate. It
compares `Shader`, `MtlFlags`, `GenMask`, `StringGenMask`, and `PublicParams` by
material name.

Fallback MTL generation is still allowed, but it is degraded. Some emitted
values are source-backed defaults, while others are compatibility-preserved
until stronger round-trip evidence exists. In particular, fallback shader masks,
`PublicParams`, default `TexMod`, `Specular`, and `Shininess` must stay visible
as compatibility evidence and must not be treated as fully proven CryEngine
material state.

`tools.mtl_schema_report` exposes this through fallback provenance counters such
as `compatibility_preserved_default_count`,
`material_attribute_compatibility_defaults`,
`public_param_compatibility_defaults`, and `texmod_compatibility_statuses`.
When a reference override is supplied, matching values are separated into
`material_attribute_override_backed_values` and
`public_param_override_backed_values` instead of being counted as fallback
defaults.

Machine-readable entry:

```text
docs/converter_schema.json -> mtl.material_state
```

Current validation gates:

```text
tools.rc_smoke_test
tools.rc_export_gate
tools.mtl_schema_report
output_formats.texture_output_diagnostics
```

The RC material report also carries a `material_slot_evidence` table. Each row
uses the final CE slot id as the key and records the manifest material name,
request name/sub_index, generated MTL slot name, CGF `MtlName` slot name, and
whether any CGF mesh subset actually uses that material id. A trailing
`<unassigned>` row is acceptable when unused; a used unassigned material is an
action-required failure.

## Texture Output Contract

For material texture references in this converter path, `.tif` and `.dds` are
treated as the same practical CryEngine texture asset identity. RC accepts both
as source texture formats, and the texture gate groups outputs by base name plus
CE suffix rather than by extension.
The model material resolver follows the same rule: if a caller asks to probe
`tif`, it also probes `dds` for the same CE suffix, and vice versa. The requested
extension remains the first choice; the paired extension is the fallback for the
same practical CE texture.

Current exported texture output keys:

- `diff` -> `Diffuse`
- `spec` -> `Specular`
- `ddna` / `ddn` -> `Bumpmap`
- `displ` -> `Heightmap`
- `emissive` -> `Emittance`
- `sss` -> `SubSurface`
- `roughness` -> `Opacity`, observed compatibility alias
- `opacity` -> `Opacity`
