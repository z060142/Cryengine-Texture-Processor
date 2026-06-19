# Phase 1 Status Matrix

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Purpose

This matrix is the Phase 1 boundary for the current converter.

Phase 1 preserves current behavior and makes guessed or fallback behavior visible. It does not claim the converter is fully CryEngine/RC-correct yet. Phase 2 is where the remaining guessed rules are replaced with source-derived or RC-probed rules.

Status meanings:

```text
Supported: implemented and covered by automated tests or repeatable local harnesses.
Degraded: works through a fallback path, but the UI/diagnostics now label the uncertainty.
Unsupported: not implemented as a dependable workflow in Phase 1.
Phase-2-only: intentionally deferred until real CryEngine/RC evidence is available.
```

## Matrix

| Area | Phase 1 Status | Current Boundary |
| --- | --- | --- |
| Texture processing | Supported | Texture import, type classification, grouping, suffix normalization, intermediate/output generation, and batch export are preserved. Texture type semantics are centralized through `model_processing.texture_type_resolver`. |
| Model load | Supported when Blender `bpy` can import the model; degraded otherwise | Blender-loaded models carry materials, mesh slot order, and polygon usage when available. `import_only`, `dummy`, and exception states are shown in PySide model rows/details and diagnostics. Filesystem texture scans are recovery evidence, not authoritative FBX material data. |
| FBX export | Degraded compatibility path | Current PySide model export still emits FBX through the existing exporter. Processed diffuse texture paths are used when available. Missing processed texture data falls back to `<material>_diff.tif` and records `fbx_diffuse_texture_fallback`. Final CGF correctness for arbitrary assets is not guaranteed in Phase 1. |
| RC request JSON | Supported as current compatibility schema | The exporter writes `request`-root JSON for RC FBX import and keeps diagnostics out of the default RC input. Material slot ordering shares `model_processing.material_slot_table`; manifest sidecars can be used as slot source of truth. Full request schema replacement is Phase-2-only. |
| MTL export | Supported with known guessed shader-mask limits | `.mtl` generation uses shared material slot assignment and tested texture path rules. It preserves CryEngine aliases and explicit relative/absolute fallbacks. Shader `GenMask`, `StringGenMask`, and `PublicParams` are compatibility-preserved guesses until Phase 2 evidence replaces them. |
| Diagnostics | Supported | Material diagnostics are available in PySide, RC smoke reports, and `<model>.material_diagnostics.json` sidecars. Diagnostics include material slot hazards, polygon usage when known, degraded model load state, texture source modes, and texture reference evidence. |
| RC smoke | Supported as repeatable harness; environment-dependent | `tools.rc_smoke_test` can run local RC imports, emit request/MTL/CGF/cryasset bundles, and write material reports. Manifest-driven smoke can validate semantic and CGF material-id alignment when local RC and sample assets are available. It is a probe/harness, not a universal conversion guarantee. |
| Material masks | Phase-2-only for correctness; compatibility-preserved in Phase 1 | Real `.mtl` schema and shader-token evidence has been collected, but local samples show persisted `GenMask` still needs RC/Material Editor round-trip evidence. Phase 1 must not change exporter mask generation beyond tested compatibility preservation. |

## Explicit Phase 1 Non-Claims

Phase 1 does not prove:

```text
arbitrary FBX -> correct CGF for all material layouts
final CryEngine shader GenMask/StringGenMask/PublicParams generation
Material Editor round-trip correctness
complete RC request schema accuracy
final Blender plugin behavior
automatic repair of wrong source material ids
```

## Phase 2 Starting Points

Start Phase 2 from these evidence gaps:

```text
GenMask/StringGenMask/PublicParams source and round-trip behavior
material slot and polygon material id behavior for non-fixture assets
request JSON schema fields accepted/required by RC
MTL defaults, shader params, and material mask persistence
```
