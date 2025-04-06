# CryEngine 贴图处理器

一个强大的工具，用于处理和转换贴图到 CryEngine 兼容格式。此应用程序可自动化 CryEngine 项目的贴图工作流程，帮助美术师和开发人员节省时间并确保一致的贴图输出。

## 功能特点

- **贴图导入与分类**：自动检测并按类型分类贴图（漫反射、法线、高光等）
- **智能贴图分组**：将属于同一材质的相关贴图分组
- **中间格式处理**：将贴图处理成标准化的中间格式
- **CryEngine 输出生成**：创建适当的 CryEngine 贴图格式：
  - _diff（漫反射）
  - _spec（高光）
  - _ddna（法线与光泽度结合）
  - _displ（位移）
  - _emissive（自发光）
  - _sss（次表面散射）
- **高级处理选项**：
  - 将金属度/粗糙度 PBR 贴图转换为 CryEngine 高光/光泽度工作流
  - 自动生成缺失的贴图
  - 控制输出分辨率和格式
- **模型导入**：从 3D 模型中提取贴图（FBX、OBJ、DAE、3DS、BLEND）
- **批处理**：一次处理多个贴图组
- **DDS 生成**：使用 RC.exe 生成 DDS 文件
- **多语言界面**：支持英文和繁体中文

> **注意：** 模型导出功能仍在开发中，尚未在当前版本中完全实现。

## 安装

### 前提条件

- Python 3.7 或更新版本
- Pillow (PIL) 库
- NumPy（推荐版本 1.x，以与 Blender Python API 兼容）
- ImageMagick（用于高级图像处理）
- Tkinter（用于 GUI）

### 设置

1. 克隆仓库：
   ```bash
   git clone https://github.com/your-username/cryengine-texture-processor.git
   cd cryengine-texture-processor
   ```

2. 运行设置脚本来创建虚拟环境并安装依赖：
   ```bash
   python setup_env.py
   ```

3. 启动应用程序：
   ```bash
   # 在 Windows 上
   run.bat
   
   # 在 Linux/Mac 上
   ./run.sh
   ```

## 使用方法

### 导入贴图

1. 点击"导入贴图"按钮
2. 选择贴图文件（JPG、PNG、TGA、TIF 等）
3. 应用程序将自动分类贴图并分组相关的贴图

### 处理贴图

1. 检查检测到的贴图组
2. 配置导出设置：
   - 输出目录
   - 漫反射格式（反照率或漫反射_环境光遮蔽）
   - 切换法线贴图绿色通道翻转
   - 启用/禁用高光生成
   - 选择输出格式和分辨率
3. 点击"导出贴图"或"批处理"以处理所有贴图组

### 使用 3D 模型

1. 切换到"模型导入"选项卡
2. 导入 3D 模型（FBX、OBJ 等）
3. 从模型中提取贴图
4. 将提取的贴图添加到处理队列

## 技术

- **Python**：主要编程语言
- **Pillow (PIL)**：图像处理
- **NumPy**：图像处理的数值运算
- **Tkinter**：GUI 框架
- **ImageMagick**：高级图像处理操作
- **Blender Python API (bpy)**：可选的模型加载支持

## 已知限制

- 模型导出功能仍在开发中
- 某些高级 PBR 工作流转换可能需要手动调整
- 要进行适当的 DDS 生成，必须在首选项中配置 RC.exe 路径
- 对于模型加载功能，需要 Blender Python API (bpy)

## 许可证

本项目采用 MIT 许可证 - 详见 LICENSE 文件。

## 致谢

- CryEngine 提供的贴图格式规范
- Pillow 和 NumPy 社区提供的出色图像处理库
- 帮助改进应用程序的贡献者和测试人员