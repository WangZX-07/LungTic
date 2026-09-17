# 基于 U-Net 的 4D 肺癌诊断与预测 — UI 系统设计文档

> 版本: v1.1 | 日期: 2026-06-02 | 应用名称: LungTic

---

## 1. 摘要

LungTic 是为"基于 U-Net 的 4D 肺癌诊断与预测"竞赛项目开发的桌面端可视化系统。系统接收 4D CT DICOM 影像，通过用户自定义的 AI 模型（.pth / .onnx）自动分割肺部肿瘤，融合生成 IGTV，并预测肿瘤运动轨迹。UI 部分使用 Electron + Vue 3 构建，遵循 8pt Grid 设计系统。

---

## 2. 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 桌面壳 | Electron 30+ | 跨平台桌面容器 |
| 前端 | Vue 3 + Vite + TypeScript | SPA 渲染进程 |
| UI 组件 | Element Plus / Naive UI | 企业级组件库 |
| 3D 渲染 | Three.js | IGTV 三维可视化 |
| 图表 | ECharts | 运动轨迹曲线 |
| DICOM 渲染 | Cornerstone.js | 医学影像 Canvas 渲染 |
| 后端 | FastAPI (Python 3.10+) | REST + WebSocket |
| AI 框架 | PyTorch 2.x + ONNX Runtime | U-Net 分割 + LSTM 预测 |
| DICOM 解析 | pydicom + SimpleITK | 医学影像 I/O |
| 数据库 | MySQL 8.0 | 结构化数据持久化 |
| ORM | SQLAlchemy 2.0 | Python 数据库映射 |
| 认证 | JWT (PyJWT) | 无状态 Token 认证 |
| 设计系统 | 8pt Grid | 全部间距/圆角/字号基于 8 的倍数 |
| Logo | ui/logo.jpg | 品牌标识 |

---

## 3. 系统架构

```
+--------------------------------------------------+
|                Electron 桌面壳                     |
|  +--------------------------------------------+  |
|  |          Vue 3 渲染进程 (前端)               |  |
|  |  Login -> Dashboard (3 Views)              |  |
|  |  Cornerstone / Three.js / ECharts          |  |
|  +------------------+-------------------------+  |
|                     |  HTTP REST + WebSocket      |
|  +------------------v-------------------------+  |
|  |      FastAPI 后端 (Python 子进程)            |  |
|  |  +--------+ +--------+ +---------------+   |  |
|  |  | Auth   | | DICOM  | | AI Engine     |   |  |
|  |  | JWT    | | Parser | | U-Net + LSTM  |   |  |
|  |  +--------+ +--------+ +---------------+   |  |
|  +------------------+-------------------------+  |
|                     | SQLAlchemy                  |
|  +------------------v-------------------------+  |
|  |             MySQL 数据库                     |  |
|  +--------------------------------------------+  |
+--------------------------------------------------+
```

**核心数据流**:
1. 用户登录 -> JWT 签发
2. DICOM 上传 -> pydicom 解析 -> 入库 + 文件存储
3. 用户上传自定义模型 (.pth/.onnx) -> 后端加载 -> 模型注册
4. 选择模型执行分割 -> U-Net 推理 -> mask 返回 -> 前端叠加
5. 预测请求 -> LSTM 推理 -> 轨迹返回 -> ECharts 渲染

---

## 4. 数据库设计

### 4.1 表结构

**users** — 系统用户
| 字段 | 类型 | 约束 |
|------|------|------|
| id | INT | PK, AUTO_INCREMENT |
| username | VARCHAR(64) | UNIQUE, NOT NULL |
| password_hash | VARCHAR(256) | NOT NULL |
| role | ENUM('doctor','admin') | DEFAULT 'doctor' |
| created_at | DATETIME | DEFAULT NOW() |

**patients** — 患者（脱敏）
| 字段 | 类型 | 约束 |
|------|------|------|
| id | INT | PK, AUTO_INCREMENT |
| patient_code | VARCHAR(32) | UNIQUE, NOT NULL |
| age_range | VARCHAR(16) | |
| gender | CHAR(1) | |
| created_at | DATETIME | DEFAULT NOW() |

**studies** — 检查记录
| 字段 | 类型 | 约束 |
|------|------|------|
| id | INT | PK, AUTO_INCREMENT |
| patient_id | INT | FK -> patients.id |
| study_uid | VARCHAR(128) | UNIQUE |
| study_date | DATE | |
| phase_count | INT | DEFAULT 10 |

**series** — DICOM 序列（按时相拆分）
| 字段 | 类型 | 约束 |
|------|------|------|
| id | INT | PK, AUTO_INCREMENT |
| study_id | INT | FK -> studies.id |
| series_uid | VARCHAR(128) | |
| phase_index | INT | 0-9 |
| slice_count | INT | |

**slices** — 单张切片元数据
| 字段 | 类型 | 约束 |
|------|------|------|
| id | INT | PK, AUTO_INCREMENT |
| series_id | INT | FK -> series.id |
| file_path | VARCHAR(512) | 相对存储路径 |
| slice_index | INT | Z 轴序号 |
| z_position | FLOAT | 物理 Z 坐标 |

**segmentations** — 分割结果
| 字段 | 类型 | 约束 |
|------|------|------|
| id | INT | PK, AUTO_INCREMENT |
| slice_id | INT | FK -> slices.id, UNIQUE |
| mask_path | VARCHAR(512) | 分割 mask 文件 |
| dice_score | FLOAT | Dice 系数 |
| model_version | VARCHAR(32) | 模型版本号 |
| created_at | DATETIME | DEFAULT NOW() |

**igtv_results** — IGTV 重建结果
| 字段 | 类型 | 约束 |
|------|------|------|
| id | INT | PK, AUTO_INCREMENT |
| study_id | INT | FK -> studies.id, UNIQUE |
| volume_cc | FLOAT | 体积(cc) |
| mesh_path | VARCHAR(512) | 3D mesh 文件 |
| created_at | DATETIME | DEFAULT NOW() |

**trajectories** — 运动轨迹
| 字段 | 类型 | 约束 |
|------|------|------|
| id | INT | PK, AUTO_INCREMENT |
| study_id | INT | FK -> studies.id |
| phase_index | INT | 0-9 |
| x_pos | FLOAT | 左右方向(mm) |
| y_pos | FLOAT | 前后方向(mm) |
| z_pos | FLOAT | 头脚方向(mm) |
| is_predicted | TINYINT | 0=真实, 1=预测 |

**user_models** — 自定义模型注册表 **[新增]**
| 字段 | 类型 | 约束 |
|------|------|------|
| id | INT | PK, AUTO_INCREMENT |
| user_id | INT | FK -> users.id |
| model_name | VARCHAR(128) | 用户自定义名称 |
| model_type | ENUM('pth','onnx') | 模型格式 |
| task_type | ENUM('segmentation','prediction') | 任务类型 |
| file_path | VARCHAR(512) | 模型文件存储路径 |
| is_active | TINYINT | 是否启用 |
| uploaded_at | DATETIME | DEFAULT NOW() |

**oauth_tokens** — OAuth 预留
| 字段 | 类型 | 约束 |
|------|------|------|
| id | INT | PK, AUTO_INCREMENT |
| user_id | INT | FK -> users.id |
| provider | VARCHAR(32) | oauth provider |
| access_token | TEXT | |
| refresh_token | TEXT | |
| expires_at | DATETIME | |

---

## 5. API 接口设计

### 5.1 认证 `/api/auth`

| 方法 | 路径 | 请求体 | 响应 | 说明 |
|------|------|--------|------|------|
| POST | `/api/auth/login` | {username, password} | {access_token, refresh_token, user} | 登录 |
| POST | `/api/auth/refresh` | {refresh_token} | {access_token} | 刷新 |
| GET | `/api/auth/me` | Header: Bearer token | {user} | 当前用户 |

### 5.2 DICOM `/api/dicom`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/dicom/upload` | 批量上传 DICOM 文件 |
| GET | `/api/patients` | 患者列表(分页) |
| GET | `/api/patients/{id}` | 患者详情 |
| GET | `/api/patients/{id}/studies` | 患者检查列表 |
| GET | `/api/studies/{id}/phases` | 检查的时相摘要 |
| GET | `/api/studies/{id}/slices?phase=X` | 时相的切片列表 |

### 5.3 自定义模型管理 `/api/models` **[新增]**

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/models/upload` | 上传模型文件 (.pth/.onnx)，body: multipart + model_name + task_type |
| GET | `/api/models` | 当前用户模型列表 |
| PUT | `/api/models/{id}/activate` | 激活指定模型 |
| DELETE | `/api/models/{id}` | 删除模型 |

### 5.4 AI 分割 `/api/segmentation`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/segmentation/run` | 执行分割(body: {study_id, model_id?})，不传 model_id 则用当前激活模型 |
| GET | `/api/segmentation/{study_id}/result` | 分割汇总结果 |
| GET | `/api/segmentation/slice?study_id=X&phase=Y&index=Z` | 单切片原图+mask(base64) |

### 5.5 IGTV `/api/igtv`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/igtv/reconstruct` | 生成 IGTV(body: {study_id}) |
| GET | `/api/igtv/{study_id}` | IGTV 结果(体积+mesh) |

### 5.6 轨迹预测 `/api/trajectory`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/trajectory/predict` | 执行预测(body: {study_id, model_id?}) |
| GET | `/api/trajectory/{study_id}` | 真实+预测轨迹对比 |

### 5.7 WebSocket `/ws`

| 事件 | payload | 说明 |
|------|---------|------|
| `segmentation_progress` | {study_id, phase, slice, total, progress} | 分割进度 |
| `reconstruction_progress` | {study_id, progress} | 重建进度 |

### 5.8 鉴权

所有 `/api/*` 请求需携带 `Authorization: Bearer <access_token>`。

---

## 6. 前端设计

### 6.1 路由

```
/                         redirect -> /login
/login                    LoginPage
/dashboard                DashboardLayout
  /dashboard/patients     PatientList
  /dashboard/models       ModelManager [新增]
  /dashboard/study/:id    StudyWorkspace
    tab: axial            AxialView
    tab: 3d               Target3DView
    tab: trajectory       TrajectoryView
```

### 6.2 组件树

```
App.vue
+-- LoginPage.vue
|     (登录表单，LungTic Logo + 品牌标识)
+-- DashboardLayout.vue
    +-- Sidebar.vue
    |     (Logo + 患者列表 + 检查列表 + 模型管理入口)
    +-- TopBar.vue (用户信息 + 退出)
    +-- <router-view>
        +-- StudyWorkspace.vue
        |   +-- PhaseSelector.vue
        |   +-- AxialView.vue [tab]
        |   |   +-- DICOMCanvas (Cornerstone.js)
        |   |   +-- MaskOverlay
        |   |   +-- SliceSlider
        |   +-- Target3DView.vue [tab]
        |   |   +-- ThreeJSViewer
        |   |   +-- IGTVInfo
        |   +-- TrajectoryView.vue [tab]
        |       +-- TrajectoryChart (ECharts)
        |       +-- PredictionToggle
        |
        +-- ModelManager.vue [新增]
            +-- ModelUpload.vue (拖拽上传 .pth/.onnx)
            +-- ModelList.vue (模型卡片列表)
            +-- ModelActivate.vue (激活/停用切换)
```

### 6.3 视图详细说明

**登录页 (LoginPage)**:
- 居中卡片布局
- LungTic Logo 在上方
- 用户名 + 密码表单
- 登录按钮

**横断面视图 (AxialView)**:
- 左侧: CT 切片 Canvas，可滑动切换层数和时相
- 右侧: mask 叠加开关 + Dice 系数显示 + 当前激活模型名称
- 底部: 时相选择滑块 (0-9) + 层数滑块

**3D 靶区视图 (Target3DView)**:
- 中央: Three.js 渲染 IGTV 三维 mesh
- 支持旋转、缩放、平移
- 右侧信息卡: 体积(cc)、Dice 均值、模型版本

**运动轨迹视图 (TrajectoryView)**:
- ECharts 三条曲线: X(左右)、Y(前后)、Z(头脚)
- 横轴: 时相(0-9)，纵轴: 位移(mm)
- 真实轨迹用实线，预测轨迹用虚线

**模型管理页 (ModelManager) [新增]**:
- 拖拽上传区域: 支持 .pth / .onnx 文件
- 表单: 模型名称 + 任务类型(分割/预测) 下拉选择
- 模型卡片列表: 显示名称/格式/任务类型/上传时间/激活状态
- 每张卡片: 激活开关 + 删除按钮
- 同一任务类型只能激活一个模型

### 6.4 8pt Grid 设计系统

所有间距、内边距、圆角、字号基于 8 的倍数：

| 层级 | 基准值 | 用途 |
|------|--------|------|
| xs | 4px (0.5x) | 图标内边距、紧凑间距 |
| sm | 8px (1x) | 组件内部间距、标签间距 |
| md | 16px (2x) | 卡片内边距、表单项间距 |
| lg | 24px (3x) | 区块间距、页面边距 |
| xl | 32px (4x) | 大区块分隔 |
| 2xl | 48px (6x) | 页面级间距 |
| 3xl | 64px (8x) | Hero 区域 |

| 元素 | 尺寸 |
|------|------|
| 侧边栏宽度 | 256px (32x8) |
| 卡片圆角 | 8px |
| 按钮高度 | 40px (5x8) |
| 输入框高度 | 40px |
| 标题字号 | 24px / 20px / 16px |
| 正文字号 | 14px |
| 小字 | 12px |

### 6.5 配色 & 品牌

- 应用名称: **LungTic**
- Logo 路径: `ui/logo.jpg`
- 主色调: 从 Logo 提取（默认医疗蓝 #1E88E5）
- 背景: #F5F7FA
- 侧边栏: 深色 #1E293B

---

## 7. AI 模型接口约定

### 7.1 自定义模型加载

**上传**: .pth 或 .onnx 文件, POST multipart 到 `/api/models/upload`
**存储**: `backend/data/models/{user_id}/{model_id}/`
**加载**: 后端根据 model_type 选择 PyTorch (`torch.load`) 或 ONNX Runtime (`onnxruntime.InferenceSession`)
**接口约束**:
- .pth: 需为 `torch.jit.script` 或完整 state_dict，后端提供标准 wrapper 模板
- .onnx: 输入/输出节点名约定为 `input` / `output`

### 7.2 Attention U-Net 分割

**输入**: DICOM 序列路径列表
**输出**: 每张切片二值 mask (.npy)，Dice 系数
**模型选择**: 优先使用用户激活的自定义分割模型，否则使用内置默认模型

### 7.3 LSTM 轨迹预测

**输入**: 前 N 个时相的分割质心序列
**输出**: 后续时相预测质心序列
**模型选择**: 同分割逻辑

---

## 8. 项目目录结构

```
ui/
+-- logo.jpg                   # 应用 Logo
+-- docs/superpowers/specs/    # 设计文档
+-- canva-design/              # Canva 导出设计稿
+-- database/
|   +-- schema.sql             # 建表语句
|   +-- seed.sql               # 初始数据
+-- backend/
|   +-- main.py                # FastAPI 入口
|   +-- config.py              # 配置
|   +-- models/
|   |   +-- db.py              # SQLAlchemy models
|   |   +-- unet.py            # Attention U-Net (内置默认)
|   |   +-- lstm.py            # LSTM 预测 (内置默认)
|   |   +-- onnx_loader.py     # ONNX 模型加载器 [新增]
|   +-- routers/
|   |   +-- auth.py
|   |   +-- dicom.py
|   |   +-- models.py          # 模型管理 API [新增]
|   |   +-- segmentation.py
|   |   +-- igtv.py
|   |   +-- trajectory.py
|   +-- services/
|   |   +-- dicom_parser.py
|   |   +-- inference.py       # 推理引擎(支持 pth/onnx)
|   |   +-- igtv_reconstruct.py
|   +-- data/
|   |   +-- models/            # 用户上传的模型文件
|   |   +-- dicom/             # DICOM 文件存储
|   +-- requirements.txt
+-- frontend/
|   +-- electron/
|   |   +-- main.js
|   |   +-- preload.js
|   +-- src/
|   |   +-- main.ts
|   |   +-- App.vue
|   |   +-- router/
|   |   +-- views/
|   |   |   +-- LoginPage.vue
|   |   |   +-- DashboardLayout.vue
|   |   |   +-- StudyWorkspace.vue
|   |   |   +-- ModelManager.vue    [新增]
|   |   +-- components/
|   |   |   +-- AxialView.vue
|   |   |   +-- Target3DView.vue
|   |   |   +-- TrajectoryView.vue
|   |   |   +-- ModelUpload.vue     [新增]
|   |   |   +-- ModelCard.vue       [新增]
|   |   +-- api/
|   |   +-- stores/
|   |   +-- styles/
|   |       +-- grid.css            # 8pt Grid 系统 [新增]
|   +-- package.json
|   +-- vite.config.ts
+-- README.md
```

---

## 9. 测试计划

| 测试类型 | 范围 | 工具 |
|----------|------|------|
| API 单元测试 | 每个 route handler + service | pytest + httpx |
| 模型管理测试 | 上传/激活/删除 .pth/.onnx | pytest |
| AI 模型测试 | 分割精度 (Dice>0.85), 预测 MSE | pytest + numpy |
| 前端组件测试 | 登录/路由/视图/模型上传 | Vitest + Vue Test Utils |
| 8pt Grid 视觉测试 | 间距/字号/圆角合规 | Storybook / 手工审查 |
| 集成测试 | 上传 DICOM -> 选模型 -> 分割 -> 显示 | pytest |
| E2E | Electron 端到端 | Playwright |

---

## 10. 开发顺序

| 阶段 | 内容 | 预估 |
|------|------|------|
| Phase 0 | Canva 设计稿 + 环境搭建 | 1天 |
| Phase 1 | MySQL schema + FastAPI 骨架 + Auth | 2天 |
| Phase 2 | DICOM 上传/解析/入库 | 2天 |
| Phase 3 | Model 管理 API (上传/激活/删除) | 1天 |
| Phase 4 | Electron + Vue 脚手架 + 8pt Grid + Login | 2天 |
| Phase 5 | Dashboard 布局 + 三视图骨架 | 3天 |
| Phase 5.5 | ModelManager 页 (上传/列表/激活) | 1天 |
| Phase 6 | AI 模型集成 (U-Net, LSTM, IGTV) | 5天 |
| Phase 7 | 前后端联调 + WebSocket 进度 | 3天 |
| Phase 8 | 测试 + 打包 | 2天 |

---

## 11. v1.1 变更记录

| 变更 | 说明 |
|------|------|
| 应用名称 | 正式命名为 **LungTic** |
| Logo | `ui/logo.jpg`，待用户提供 |
| 8pt Grid | 全界面间距/圆角/字号基于 8 的倍数 |
| 自定义模型 | 新增 ModelManager 页面 + API，支持 .pth/.onnx 上传/激活/删除 |
| 数据库 | 新增 `user_models` 表 |

---

## 12. 假设 & 默认决策

1. **OAuth**: 预留接口但首版不实现，仅 JWT 登录
2. **AI 模型**: 内置默认 U-Net/LSTM，用户可上传自定义 .pth/.onnx 替换
3. **DICOM 存储**: 文件存储在 `backend/data/dicom/`，数据库仅存元数据路径
4. **模型存储**: 用户模型存储在 `backend/data/models/{user_id}/`
5. **Electron 打包**: 首版不含 Python 环境打包
6. **Windows 优先**: macOS/Linux 兼容但不优先
7. **Logo**: `ui/logo.jpg`，CSS 变量预留品牌色
8. **8pt Grid**: 所有新建组件严格遵循，使用 CSS 变量 `--space-{n}`

---

> 文档结束。下一阶段: 实施计划 (writing-plans)。
