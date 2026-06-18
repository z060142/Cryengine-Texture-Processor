# Refactor Phase 8: CGF Material Subset Reader

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Move from input-side material alignment to output-side evidence. Phase 7 proved the generated RC request and `.mtl` agree on sub-material slots. This phase reads the generated `.cgf` and extracts the material ids RC actually wrote into mesh subsets.

## CryEngine Source Evidence

Relevant source files in `S:\Crytek\crytek\CRYENGINE_Source-release`:

```text
Code\CryEngine\Cry3DEngine\CGF\ChunkFileComponents.h
Code\CryEngine\CryCommon\Cry3DEngine\CGF\CryHeaders.h
Code\CryEngine\Cry3DEngine\CGF\CGFLoader.cpp
Code\CryEngine\Cry3DEngine\CGF\ChunkFileReaders.cpp
```

Important facts:

- 0x746 chunk files use `CrCh` as the file signature.
- The 0x746 header stores `version`, `chunkCount`, and `chunkTableOffset`.
- Each 0x746 chunk table entry stores:
  - `type`
  - `version`
  - `id`
  - `size`
  - `offsetInFile`
- `ChunkType_Mesh = 0x1000`.
- `ChunkType_MeshSubsets = 0x1017`.
- `MESH_CHUNK_DESC_0801` stores `nSubsets`, `nSubsetsChunkId`, and stream chunk ids.
- `MESH_SUBSETS_CHUNK_DESC_0800::MeshSubset.nMatID` is documented as the "Material sub-object Id".
- `CGFLoader.cpp` copies that field into `SMeshSubset.nMatID`.

This gives us the exact CGF-side field to inspect:

```text
MeshSubsets.MeshSubset.nMatID
```

## What Changed

- Added `utils/cgf_material_reader.py`.
- Added `tools/cgf_material_probe.py`.
- `tools/material_mapping_report.py` now includes:
  - `cgf_material_summary`
  - `cgf_read_error`
  - `cgf_material_id_alignment`
- Added tests for synthetic 0x746 CGF chunk tables and MeshSubsets parsing.

## CLI

Inspect an existing CGF:

```powershell
uv run python -m tools.cgf_material_probe "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_materials\CubeA_material_probe.cgf"
```

## Real RC Output Observation

After rerunning the material smoke:

```powershell
uv run python -m tools.rc_smoke_test --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_materials" --asset-name "CubeA_material_probe" --materials "Default,Detail,collision_proxy"
```

The refreshed report contained:

```json
{
  "cgf_read_error": "",
  "cgf_material_summary": {
    "chunk_count": 12,
    "material_ids": [0],
    "meshes": [
      {
        "chunk_id": 10,
        "verts": 24,
        "indices": 36,
        "subset_count": 1,
        "subsets_chunk_id": 4,
        "subsets": [
          {
            "subset": 0,
            "num_indices": 36,
            "material_id": 0
          }
        ]
      }
    ]
  },
  "cgf_material_id_alignment": {
    "ok": true,
    "material_ids": [0]
  }
}
```

Interpretation:

- The sample GameSDK `CubeA.fbx` only produced one CGF mesh subset.
- That subset used material id `0`.
- Material id `0` exists in both the RC request and generated `.mtl` slot list, where it maps to `Default`.
- The extra request/MTL slots `Detail` and `collision_proxy` were valid inputs but were not referenced by this sample mesh.

## Boundary

We can now inspect final CGF subset material ids. We still need a controlled FBX fixture whose faces intentionally use multiple material slots. Without that, the current GameSDK cube only proves slot 0 survives end to end.

## Verification

Passed:

```powershell
uv run python -m pytest tests
uv run python -m tools.rc_smoke_test --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_materials" --asset-name "CubeA_material_probe" --materials "Default,Detail,collision_proxy"
uv run python -m tools.cgf_material_probe "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_materials\CubeA_material_probe.cgf"
```

## Remaining Work

- Generate a small Blender FBX with two or three actual face material assignments.
- Run it through the same RC smoke path.
- Confirm CGF `MeshSubsets.nMatID` contains the expected material ids.
- Use that fixture to lock the material-id rules for the future Blender plugin/exporter path.
