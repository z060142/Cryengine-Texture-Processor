# CryEngine Texture Processor

[中文版说明](https://github.com/z060142/Cryengine-Texture-Processor/blob/main/README_ZH.md)

A powerful tool for processing and converting textures to CryEngine-compatible formats. This application automates the texture workflow for CryEngine projects, helping artists and developers save time and ensure consistent texture outputs.

## Features

- **Texture Import & Classification**: Automatically detects and classifies textures by type (diffuse, normal, specular, etc.)
- **Smart Texture Grouping**: Groups related textures that belong to the same material
- **Intermediate Format Processing**: Processes textures into standardized intermediate formats
- **CryEngine Output Generation**: Creates proper CryEngine texture formats:
  - _diff (Diffuse)
  - _spec (Specular)
  - _ddna (Normal & Gloss combined)
  - _displ (Displacement)
  - _emissive (Emissive)
  - _sss (Subsurface Scattering)
- **Advanced Processing Options**:
  - Convert Metallic/Roughness PBR textures to CryEngine spec/gloss workflow
  - Automatically generate missing textures
  - Control output resolution and format
- **Model Import**: Extract textures from 3D models (FBX, OBJ, DAE, 3DS, BLEND)
- **RC Import Request Export**: Generate `request`-root JSON files for CryEngine Resource Compiler FBX conversion
- **Batch Processing**: Process multiple texture groups at once
- **DDS Generation**: Generate DDS files using RC.exe
- **Multilingual Interface**: Support for English and Traditional Chinese

> **Note:** The model export functionality is still under development and not fully implemented in the current version.

## Installation

### Prerequisites

- Python 3.10 or newer
- uv
- Pillow (PIL) library
- NumPy (version 1.x recommended for compatibility with Blender Python API)
- PySide6
- ImageMagick (for advanced image processing)
- Blender Python API (bpy), optional for model loading/export support

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/cryengine-texture-processor.git
   cd cryengine-texture-processor
   ```

2. Sync the environment with uv:
   ```bash
   uv sync
   ```

   If you need Blender Python API support and your Python version has a compatible `bpy` wheel:
   ```bash
   uv sync --extra model
   ```

3. Start the PySide application:
   ```bash
   uv run python main.py
   ```

The old Tkinter entry point is preserved as `legacy_tk_main.py` during the migration.

## Usage

### Importing Textures

1. Click the "Import Textures" button
2. Select texture files (JPG, PNG, TGA, TIF, etc.)
3. The application will automatically classify textures and group related ones

### Processing Textures

1. Review the detected texture groups
2. Configure export settings:
   - Output directory
   - Diffuse format (albedo or diffuse_ao)
   - Toggle normal map green channel flip
   - Enable/disable specular generation
   - Select output format and resolution
3. Click "Export Textures" or "Batch Process" to process all texture groups

### Working with 3D Models

1. Switch to the "Model Import" tab
2. Import a 3D model (FBX, OBJ, etc.)
3. Extract textures from the model
4. Add extracted textures to the processing queue

### RC FBX Smoke Test

The repository includes a repeatable smoke harness for CryEngine Resource Compiler FBX conversion:

```bash
uv run python -m tools.rc_smoke_test --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_default" --asset-name "CubeA_default_smoke" --materials "Default"
```

When local CryEngine 5.7.1 and GameSDK sample folders are present, the harness discovers `rc.exe` and `objects\cubao\CubeA.fbx` automatically. The verified run writes a `.fbx`, `.mtl`, `.json`, `.cgf`, and `.cryasset` bundle under the selected work directory.

The harness also writes `<asset>.material_report.json`, which compares RC request material `sub_index` values with generated `.mtl` sub-material slots.

## Technologies

- **Python**: Main programming language
- **Pillow (PIL)**: Image processing
- **NumPy**: Numerical operations for image processing
- **PySide6**: GUI framework
- **ImageMagick**: Advanced image processing operations
- **Blender Python API (bpy)**: Optional model loading support

## Known Limitations

- Model export functionality is still under development
- Certain advanced PBR workflow conversions may require manual tweaking
- For proper DDS generation, RC.exe path must be configured in preferences
- For model loading functionality, Blender Python API (bpy) is required or must be provided through a later Blender subprocess integration
- RC request generation now aligns material sub-indices with existing `.mtl` submaterial slots where possible; true FBX material-id extraction still needs a later pass
- RC execution now uses a structured runner; a real `rc.exe` smoke test has passed with the local GameSDK `CubeA.fbx` sample
- A repeatable RC smoke harness is available via `uv run python -m tools.rc_smoke_test`
- Smoke runs now emit a material mapping report; final `.cgf` material table inspection still needs a later CryEngine-aware reader or editor-side check

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- CryEngine for their texture format specifications
- The Pillow and NumPy communities for their excellent image processing libraries
- Contributors and testers who have helped improve the application
