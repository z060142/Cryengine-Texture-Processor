# Refactor Phase 1: PySide Shell, uv, and Material Resolver

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

This phase starts the larger rewrite without deleting the rough but useful old tool. The immediate target is to keep the existing conversion behavior recognizable while creating better seams for the real CryEngine/RC rules that will come next.

## What Changed

- `main.py` is now the PySide6 entry point.
- The previous Tkinter entry point was preserved as `legacy_tk_main.py`.
- A new `ui_pyside/` package provides the first PySide6 UI shell:
  - main window
  - texture import panel
  - texture group panel
  - preview panel
  - model import panel
  - export settings panel
  - progress dialog
- `pyproject.toml` and `uv.lock` were added so `uv` can manage the project.
- `requirements.txt` was kept as a compatibility file, but the main workflow should move to `uv`.
- `model_processing/material_texture_resolver.py` now centralizes the existing material-to-processed-texture lookup rules.
- `output_formats/json_exporter.py` and `output_formats/mtl_exporter.py` now share the material cleanup helper for:
  - ignoring Blender placeholder materials like `Material` and `Dots Stroke`
  - stripping Blender duplicate suffixes like `.001`
  - keeping contiguous generated sub-material indices for the current legacy JSON path

## Current PySide Coverage

The PySide UI is a first working shell, not the final polished application. It covers the main interaction paths:

- import texture files
- classify/reclassify/delete imported textures
- show detected texture groups
- preview selected textures
- import model files
- list model materials and extracted textures
- add extracted model textures into the texture processing queue
- configure output directories and export options
- trigger texture export, model export, and batch export

The PySide model import is currently synchronous. The old Tkinter UI used a worker thread and queue. The next UI pass should move model import and export work to `QThread` or `QThreadPool` so the UI does not block during Blender/bpy work.

## uv Notes

Use:

```powershell
uv sync
uv run python main.py
```

Blender's `bpy` package has narrow Python version support, so it is guarded behind the optional `model` extra with version markers:

```powershell
uv sync --extra model
```

On Python versions where no compatible `bpy` wheel exists, model import/export will still depend on an external Blender Python setup or a later subprocess-based Blender integration.

## Material Resolver Behavior Kept From Legacy Tool

For each model material, the resolver:

1. skips known default materials
2. asks `TextureManager.classify_texture()` for the texture base name when the source texture exists
3. falls back to stripping common suffixes such as `_diff`, `_albedo`, `_normal`, `_ddna`, `_spec`, `_height`, `_emissive`
4. searches the processed texture output directory for current legacy outputs:
   - FBX shader rewrite: `_diff`, `_ddna`
   - MTL export: `_diff`, `_ddna`, `_spec`, `_displ`, `_emissive`, `_opacity`, `_sss`

This is still legacy behavior. It is not yet the CryEngine Editor's exact material auto-assignment algorithm.

## Verification

Passed:

```powershell
python -m compileall main.py legacy_tk_main.py model_processing ui_pyside output_formats
python -m pytest tests
uv lock
```

`uv run --with pytest pytest tests` was attempted, but timed out during first-time environment setup/download. The lockfile itself resolves successfully.

## Known Gaps For The Next Phase

- Replace the legacy JSON root/schema with RC-compatible `request` generation.
- Implement CryEngine material sub-index assignment accurately:
  - existing `.mtl` submaterial name match
  - preserve FBX material id when valid
  - fill free slots deterministically
  - encode deleted materials as `sub_index = -1`
- Replace the current synchronous PySide model import with Qt worker threads.
- Move model export orchestration out of `main.py` into a service/controller module.
- Validate PySide runtime after `uv sync` installs PySide6 in a fresh environment.
- Decide whether `bpy` should be embedded, optional, or driven through a Blender subprocess.
- Update README/setup docs so new users stop following the old Tkinter/venv path.
