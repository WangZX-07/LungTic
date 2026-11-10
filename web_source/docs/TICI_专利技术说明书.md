# .tiCi 格式技术说明书

## 用于发明专利申报的完整技术文档

---

## 一、技术领域

本发明涉及医学影像数据存储与交换技术领域，具体涉及一种基于 HDF5 分层容器架构的时序医学影像一体化文件格式（.tiCi，Time-series Image Continuum），用于将多时间相位的三维医学影像数据、AI 辅助分析结果（肿瘤分割掩膜、靶区重建、运动轨迹预测）及其完整溯源信息封装于单一文件中，实现跨系统、跨平台的高效数据交换与持久化存储。

---

## 二、背景技术

### 2.1 现有技术问题

当前医学影像领域存在以下技术瓶颈：

**(1) DICOM 文件的碎片化问题**

DICOM（Digital Imaging and Communications in Medicine）标准将每次 CT/MRI 扫描的每一层切片存储为独立文件。一个典型的 4D CT 扫描（10 个呼吸时相 × 100 层切片）会产生 1000+ 个独立文件。这种碎片化导致：
- 文件管理复杂，传输易丢失
- 元数据在每文件中冗余重复，存储效率低
- 缺乏对时间维度的原生支持

**(2) NIfTI 格式的局限性**

NIfTI（Neuroimaging Informatics Technology Initiative）格式虽然支持 4D 数据（X, Y, Z, T），但：
- 不支持 AI 分析衍生数据的嵌入（分割掩膜、靶区轮廓、运动轨迹等）
- 元数据模型简化，丢失 DICOM 丰富的临床信息
- 缺乏可扩展的层次化存储结构
- 不支持分层压缩策略

**(3) 现有格式缺乏 AI 管线集成能力**

随着 AI 辅助诊断的普及，医学影像数据需要与分割掩膜、三维靶区重建、运动轨迹预测等 AI 分析结果关联存储。现有格式均无法在原位（in-place）存储和增量追加这些衍生数据。

### 2.2 本发明要解决的技术问题

1. 如何将多时间相位的三维医学影像及其 AI 分析结果封装为单一文件
2. 如何在保证数据完整性的前提下实现分层压缩以优化存储效率
3. 如何支持渐进式写入，适配 AI 推理管线的多阶段数据追加需求
4. 如何实现跨系统的格式自描述与溯源机制

---

## 三、发明内容

### 3.1 技术方案概述

本发明提出一种基于 HDF5（Hierarchical Data Format version 5）容器的时序医学影像文件格式 `.tiCi`（Time-series Image Continuum），其核心创新在于：

1. **层次化分组存储结构**：将患者元数据、检查参数、各时相影像数据、AI 分析结果按逻辑分组存储于 HDF5 的 Group/Dataset 树形结构中
2. **Magic Number 文件头识别**：采用 8 字节固定魔数 `\x89TICI\r\n\x1a\n` 作为文件类型标识
3. **分层压缩策略**：依据数据访问频率和特性，对不同数据层施以差异化压缩算法
4. **渐进式写入机制**：支持在 AI 管线各阶段（影像导入、分割推理、靶区重建、轨迹预测）逐步追加数据
5. **溯源追踪体系**：记录数据来源、转换工具版本、AI 模型版本等完整溯源链

### 3.2 格式规范

#### 3.2.1 文件头识别

文件首 8 字节固定为 Magic Number：`\x89TICI\r\n\x1a\n`

该设计仿 PNG 格式的魔数验证机制，防止文件类型误识别。格式版本号存储于 HDF5 根级属性 `/format_version`。

#### 3.2.2 层次化存储结构

```
.tiCi 文件 (HDF5 Container)
│
├── /patient/                         患者信息组
│   ├── @patient_id        String     患者唯一标识
│   ├── @patient_name      String     患者姓名
│   ├── @patient_sex       String     性别
│   └── @patient_age       String     年龄
│
├── /study/                           检查信息组
│   ├── @study_uid         String     检查唯一标识（DICOM StudyInstanceUID）
│   ├── @study_date        String     检查日期 (ISO 8601)
│   ├── @modality          String     成像模态 (CT/MRI/NIfTI)
│   ├── @phase_count       Int        时间相位数
│   ├── @rows              Int        图像行数（像素）
│   ├── @cols              Int        图像列数（像素）
│   ├── @slice_count       Int        每相切片数
│   ├── @pixel_spacing     Float32[2] 像素间距 (sx, sy) mm
│   ├── @slice_thickness   Float32    层厚 mm
│   └── @slice_locations   Float32[N] 各切片 z 坐标数组
│
├── /phases/                          时间序列影像组
│   ├── phase_0/                      第 0 时相
│   │   ├── images     Dataset(Z,H,W) float32   CT 影像体素数据 [gzip level4]
│   │   └── masks      Dataset(Z,H,W) uint8     分割掩膜 [lzf] (可选)
│   ├── phase_1/                      ...
│   └── phase_N/                      ...
│
├── /igtv/                            内部靶区体积组 (可选)
│   ├── @volume_cc        Float32     IGTV 体积 (立方厘米)
│   ├── @method           String      融合方法 (union/majority_vote)
│   ├── mask              Dataset     ITV 三维掩膜 [lzf]
│   └── mesh              Dataset     三维网格 (Wavefront OBJ 文本)
│
├── /trajectory/                      肿瘤运动轨迹组 (可选)
│   ├── @prediction_model String      AI 模型名称
│   ├── centroids         Dataset(N,3) 各时相肿瘤质心坐标
│   ├── observed          Dataset(7,3) 观测轨迹 (前7时相)
│   └── predicted         Dataset(3,3) 预测轨迹 (后3时相)
│
└── /provenance/                      数据溯源组
    ├── @source_type       String     数据来源类型 (dicom/nifti)
    ├── @source_files_count Int       原始文件数量
    ├── @converter_version String     转换器版本
    ├── @conversion_date   String     转换时间 (ISO 8601)
    └── @model_version     String     AI 模型版本
```

#### 3.2.3 分层压缩策略

| 数据层 | 压缩算法 | 压缩级别 | 设计依据 |
|--------|----------|----------|----------|
| `/phases/*/images` | gzip | level 4 | CT 影像空间冗余度高，无损压缩比约 3:1；gzip 为医学界广泛认可 |
| `/phases/*/masks` | lzf (类 lz4) | 默认 | 分割掩膜被 AI 管线频繁读写，需快速随机访问 |
| `/igtv/mask` | lzf | 默认 | 同上，高频访问数据 |
| `/trajectory/*` | 不压缩 | - | 数据量极小 (< 1KB)，压缩无收益 |
| 所有 HDF5 Attributes | 不压缩 | - | 元数据需即时读取，不应有解压延迟 |

### 3.3 核心算法与数据结构

#### 3.3.1 文件创建算法

```
Algorithm: CreateTiciFile(patient_info, study_info, output_path)
Input:  patient_info  - 患者元数据字典
        study_info    - 检查参数字典
        output_path   - 输出文件路径
Output: .tiCi 文件句柄

1. 创建 HDF5 文件 output_path，模式为 "w"
2. 写入根属性:
   a. MAGIC ← bytes("\x89TICI\r\n\x1a\n")
   b. format_version ← "1.0"
3. 创建 /patient Group，逐字段写入 Attributes
4. 创建 /study Group，写入检查参数 Attributes
5. 返回文件句柄
```

#### 3.3.2 渐进式影像写入算法

```
Algorithm: WritePhaseImages(file, phase_index, images, masks)
Input:  file       - 已打开的 .tiCi 文件句柄
        phase_index - 时相编号 (0-based)
        images     - 三维数组 (Z, H, W) float32
        masks      - 三维数组 (Z, H, W) uint8 或 None

1. 定位或创建 /phases/phase_{phase_index} Group
2. 若 images Dataset 已存在，删除之
3. 创建 images Dataset:
   a. 数据类型: float32
   b. 压缩: gzip, compression_opts=4
   c. 写入 images 数据
4. 若 masks != None:
   a. 若 masks Dataset 已存在，删除之
   b. 创建 masks Dataset:
      - 数据类型: uint8
      - 压缩: lzf
      - 写入 masks 数据
```

#### 3.3.3 AI 结果追加算法

```
Algorithm: AppendAIDerivedData(file, data_type, payload)
Input:  file      - 已打开的 .tiCi 文件句柄 (mode="a")
        data_type - 数据类型: "masks" | "igtv" | "trajectory"
        payload   - 待追加数据

1. 以 "r+" 模式打开文件（保留已有数据）
2. Switch data_type:
   case "masks":
     定位 /phases/phase_N Group，追加 masks Dataset
   case "igtv":
     定位或创建 /igtv Group，写入 mask, mesh, volume_cc
   case "trajectory":
     定位或创建 /trajectory Group，写入 centroids, observed, predicted
3. 关闭文件
```

#### 3.3.4 按需读取算法

```
Algorithm: ReadPhaseImages(file_path, phase_index)
Input:  file_path   - .tiCi 文件路径
        phase_index - 目标时相编号
Output: images - 三维数组 (Z, H, W) float32

1. 以 "r" 模式打开 HDF5 文件
2. 验证 MAGIC 属性 == "\x89TICI\r\n\x1a\n"
3. 定位路径 /phases/phase_{phase_index}/images
4. 读取 Dataset 数据至内存 (numpy array)
5. 关闭文件
6. 返回 images 数组
```

### 3.4 系统集成架构

#### 3.4.1 渐进式管线集成

```
┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ DICOM    │    │ U-Net        │    │ IGTV          │    │ LSTM         │
│ 上传     │───→│ 分割推理     │───→│ 靶区重建      │───→│ 轨迹预测     │
└────┬─────┘    └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
     │                 │                   │                   │
     ▼                 ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                     .tiCi 文件 (单一文件)                        │
│                                                                 │
│  Phase 1: 写入 /patient + /study + /phases/*/images             │
│  Phase 2: 追加 /phases/*/masks                                  │
│  Phase 3: 追加 /igtv/mask + /igtv/mesh                          │
│  Phase 4: 追加 /trajectory/*                                    │
└─────────────────────────────────────────────────────────────────┘
```

各阶段写入失败不影响主流程，数据以数据库记录为准，.tiCi 追加静默降级。

#### 3.4.2 REST API 接口定义

| 端点 | 方法 | 功能 | 请求体 | 响应体 |
|------|------|------|--------|--------|
| `/api/tici/export/{study_id}` | POST | 全量导出为 .tiCi | - | `{status, tici_path, phase_count}` |
| `/api/tici/download/{study_id}` | GET | 下载 .tiCi 文件 | - | `binary/octet-stream` |
| `/api/tici/info/{study_id}` | GET | 查看元信息 | - | `{patient, study, phases, provenance, file_size}` |
| `/api/tici/preview/{study_id}` | GET | 切片预览 | query: `phase`, `slice` | `{image_base64, width, height}` |
| `/api/tici/import` | POST | 导入 .tiCi 文件 | multipart: `file` | `{status, study_id, phase_count}` |
| `/api/dicom/upload` | POST | 上传 DICOM | multipart: `files` | `{status, studies, total_files}` |

上传接口支持的文件类型：
- DICOM 文件：`.dcm`（单文件或多文件批量）
- DICOM 文件夹：通过前端 `webkitdirectory` 属性实现整个目录上传
- NIfTI 文件：`.nii`, `.nii.gz`
- TICI 文件：`.tici`（导入已封装的时序影像数据）

导出接口支持的输出格式：
- `.tici`（推荐，包含全部数据的单一文件）
- `.json`（结构化报告，含分割结果、靶区体积、轨迹坐标）
- `.dcm`（原始 DICOM 文件，可单独下载任一切片）

#### 3.4.3 Python 读写 API

**写入器接口：**

```python
class TiciWriter:
    """渐进式 .tiCi 写入器"""
    
    def __init__(self, path: str, mode: str = "w")
        # mode: "w" 创建新文件, "a" 追加到已有文件
    
    def __enter__(self) -> "TiciWriter": ...
    def __exit__(self, ...): ...
    
    def write_metadata(patient: dict, study: dict) -> None: ...
    def write_phase_images(phase_idx: int, images: np.ndarray,
                           masks: np.ndarray = None) -> None: ...
    def append_phase_masks(phase_idx: int, masks: np.ndarray) -> None: ...
    def write_igtv(mask: np.ndarray, mesh_text: str,
                   volume_cc: float, method: str = "union") -> None: ...
    def write_trajectory(centroids: np.ndarray, observed: np.ndarray,
                         predicted: np.ndarray, model_name: str = "") -> None: ...
    def write_provenance(info: dict) -> None: ...
```

**读取器接口：**

```python
class TiciReader:
    """按需读取器"""
    
    def __init__(self, path: str): ...
    def __enter__(self) -> "TiciReader": ...
    def __exit__(self, ...): ...
    
    def get_metadata(self) -> TiciMetadata: ...
    
    @property
    def phase_count(self) -> int: ...
    
    def get_phase_images(phase_idx: int) -> np.ndarray: ...
    def get_phase_masks(phase_idx: int) -> np.ndarray | None: ...
    def get_all_phases() -> list[np.ndarray]: ...
    def get_igtv() -> TiciIgtvResult | None: ...
    def get_trajectory() -> TiciTrajectoryResult | None: ...
    
    @property
    def format_version(self) -> str: ...
    
    def get_phase_meta() -> list[dict]: ...
```

### 3.5 转换器设计

#### 3.5.1 DICOM → .tiCi 转换

```
Algorithm: from_dicom_dir(dicom_dir, output_path)
Input:  dicom_dir   - 包含 .dcm 文件的目录
        output_path - 目标 .tiCi 文件路径

1. 遍历 dicom_dir，收集所有 .dcm 文件
2. 读取首个 DICOM 文件，提取患者元数据和检查参数
3. 按 InstanceNumber % 10 将切片分组为时相 (phase)
4. 各时相内按 SliceLocation 排序
5. 全局像素值归一化至 [0, 1]
6. 创建 .tiCi 文件，写入元数据
7. 逐时相堆叠切片为三维体素 (Z, H, W)，写入 images Dataset
8. 写入溯源信息 (source_type="dicom", source_files_count=N)
9. 返回 output_path
```

#### 3.5.2 NIfTI → .tiCi 转换

```
Algorithm: from_nifti(nifti_path, output_path)
Input:  nifti_path  - 4D NIfTI 文件路径 (.nii / .nii.gz)
        output_path - 目标 .tiCi 文件路径

1. 使用 nibabel 加载 NIfTI 文件，获取 data (X, Y, Z, T) 和 zooms
2. 提取各维度尺寸和像素间距
3. 全局归一化至 [0, 1]
4. 创建 .tiCi 文件，写入元数据 (modality="NIfTI")
5. 对每个时间帧 t ∈ [0, T):
   a. 提取 data[:, :, :, t] 作为单时相三维体素
   b. 写入 /phases/phase_t/images
6. 写入溯源信息 (source_type="nifti")
7. 返回 output_path
```

---

## 四、技术效果

### 4.1 存储效率对比

以典型 4D CT 扫描为例（512×512×100 slices × 10 phases × 4 bytes float32 = ~1 GB 原始数据）：

| 存储方式 | 文件数量 | 总大小 | 元数据冗余 |
|----------|----------|--------|-----------|
| 原始 DICOM | 1000+ 个 | ~1.2 GB | 每文件冗余 ~2 KB 元数据 |
| 4D NIfTI | 1 个 | ~600 MB | 元数据简化，丢失临床信息 |
| **.tiCi (本发明)** | **1 个** | **~350 MB** | **完整保留 + AI 结果嵌入** |

### 4.2 访问性能

- **部分读取**：支持按需加载单时相数据，内存占用仅为全量的 1/N
- **渐进写入**：AI 管线各阶段独立追加，无需重建整个文件
- **压缩透明度**：HDF5 内置解压，上层 API 无感知

### 4.3 兼容性与可扩展性

- 基于 HDF5 标准，跨语言（Python/C/C++/Java/MATLAB）原生支持
- 可通过新增 Group/Dataset 扩展未来 AI 分析结果类型
- Magic Number 机制确保文件类型准确识别

---

## 五、权利要求

1. 一种基于 HDF5 容器的时序医学影像文件格式，其特征在于，采用层次化分组结构将患者信息、检查参数、多时相影像体素数据、AI 分析衍生结果及数据溯源信息封装于单一文件中。

2. 如权利要求 1 所述的文件格式，其特征在于，文件头部 8 字节采用固定魔数 `\x89TICI\r\n\x1a\n` 作为格式类型标识。

3. 如权利要求 1 所述的文件格式，其特征在于，采用分层压缩策略：原始影像数据使用 gzip 无损压缩，AI 衍生数据使用 lzf/lz4 快速压缩，元数据不压缩。

4. 如权利要求 1 所述的文件格式，其特征在于，支持渐进式写入机制，允许在影像导入、分割推理、靶区重建、轨迹预测等 AI 管线各阶段分步追加数据至同一文件。

5. 如权利要求 1 所述的文件格式，其特征在于，包含 `/provenance` 溯源组，记录数据来源类型、原始文件数量、转换工具版本及 AI 模型版本，形成完整数据溯源链。

6. 如权利要求 1 所述的文件格式，其特征在于，AI 分析衍生结果包括：`/phases/phase_N/masks` 分割掩膜、`/igtv/mask` 内部靶区体积掩膜、`/igtv/mesh` 三维网格、`/trajectory/observed` 观测轨迹及 `/trajectory/predicted` 预测轨迹。

7. 一种将 DICOM 目录或 NIfTI 4D 文件转换为权利要求 1-6 任一所述格式的方法，包括按 InstanceNumber 取模分组为时相、全局像素值归一化、逐时相堆叠为三维体素并分层写入 HDF5 Group 的步骤。

8. 一种基于权利要求 1-6 任一所述格式的医学影像数据交换系统，包括：REST API 导出接口、按需下载接口、元信息查询接口及切片预览接口。

---

## 六、附图说明

### 图 1：.tiCi 格式层次结构图

```
                    ┌──────────────────────┐
                    │   .tiCi File (HDF5)  │
                    │  MAGIC: \x89TICI\r\n │
                    │  VERSION: 1.0        │
                    └──────────┬───────────┘
           ┌───────────────────┼───────────────────┐
           │                   │                   │
    ┌──────▼──────┐    ┌──────▼──────┐    ┌───────▼──────┐
    │  /patient   │    │   /study    │    │ /provenance  │
    │  Attributes │    │  Attributes │    │  Attributes  │
    └─────────────┘    └─────────────┘    └──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │         /phases              │
                    │  ┌──────────────────────┐   │
                    │  │ phase_0/              │   │
                    │  │  ├── images (gzip)    │   │
                    │  │  └── masks  (lzf)    │   │
                    │  ├── phase_1/ ...        │   │
                    │  └── phase_N/ ...        │   │
                    └──────────────────────────┘   │
           ┌───────────────────┐                    │
    ┌──────▼──────┐    ┌──────▼──────┐
    │   /igtv     │    │ /trajectory │
    │  mask+mesh  │    │ centroids   │
    │  volume_cc  │    │ observed    │
    └─────────────┘    │ predicted   │
                       └─────────────┘
```

### 图 2：渐进式管线集成流程图

```
 DICOM Upload ──→ Create .tiCi ──→ Write metadata + images
                                        │
 U-Net Segment ──→ Append masks ────────┤
                                        │
 IGTV Reconstruct ──→ Append IGTV ──────┤
                                        │
 LSTM Predict ──→ Append trajectory ────┘
                                        │
                                        ▼
                               ✅ 单一完整 .tiCi 文件
```

---

## 七、具体实施方式

### 7.1 软件开发环境

- 编程语言：Python 3.10+
- HDF5 库：h5py 3.x
- DICOM 解析：pydicom 3.x
- NIfTI 解析：nibabel
- Web 框架：FastAPI
- 前端框架：Vue 3 + Naive UI + TypeScript

### 7.2 实施示例

**示例 1：创建 .tiCi 文件并写入数据**

```python
from tici import TiciWriter
import numpy as np

with TiciWriter("patient_001.tici", "w") as tici:
    # 写入元数据
    tici.write_metadata(
        patient={"patient_id": "P001", "patient_name": "Test"},
        study={"study_uid": "1.2.840...", "phase_count": 10,
               "rows": 512, "cols": 512}
    )
    # 逐时相写入影像
    for phase in range(10):
        images = np.random.rand(100, 512, 512).astype(np.float32)
        tici.write_phase_images(phase, images)

    # 写入 IGTV
    tici.write_igtv(
        mask=np.ones((100, 512, 512), dtype=np.uint8),
        mesh_text="v 0 0 0\nv 1 0 0\n...",
        volume_cc=42.5, method="union"
    )

    # 写入轨迹
    tici.write_trajectory(
        centroids=np.random.rand(10, 3).astype(np.float32),
        observed=np.random.rand(7, 3).astype(np.float32),
        predicted=np.random.rand(3, 3).astype(np.float32),
        model_name="BiLSTM-v2"
    )
```

**示例 2：按需读取 .tiCi 文件**

```python
from tici import TiciReader

with TiciReader("patient_001.tici") as tici:
    # 快速查询元数据（不加载影像）
    meta = tici.get_metadata()
    print(f"时相数: {tici.phase_count}")
    print(f"患者: {meta.patient.patient_name}")

    # 仅加载第 3 时相的影像
    phase3_images = tici.get_phase_images(3)
    print(f"Phase 3 形状: {phase3_images.shape}")

    # 获取 AI 分析结果
    igtv = tici.get_igtv()
    if igtv:
        print(f"IGTV 体积: {igtv.volume_cc} cc")

    traj = tici.get_trajectory()
    if traj:
        print(f"预测模型: {traj.prediction_model}")
```

**示例 3：DICOM 目录转换**

```python
from tici import from_dicom_dir

# 将整个 DICOM 目录转换为单一 .tiCi 文件
from_dicom_dir(
    dicom_dir="/data/dicom/study_001",
    output_path="/data/tici/study_001.tici"
)
```

---

*文档版本：1.0*
*编制日期：2026-06-04*
*LungTic 项目组*
