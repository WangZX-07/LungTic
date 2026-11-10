# LungTic 系统架构文档

## 整体架构图

```
+====================================================+
|                Electron 桌面壳                       |
|  +----------------------------------------------+  |
|  |          Vue 3 渲染进程 (SPA)                  |  |
|  |                                              |  |
|  |  LoginPage ──> DashboardLayout               |  |
|  |                   ├── PatientList             |  |
|  |                   ├── ModelManager            |  |
|  |                   └── StudyWorkspace          |  |
|  |                        ├── AxialView          |  |
|  |                        ├── Target3DView       |  |
|  |                        └── TrajectoryView     |  |
|  |                                              |  |
|  |  State: Pinia (authStore)                    |  |
|  |  HTTP: Axios (/api proxy)                    |  |
|  +-----------------------+----------------------+  |
|                          | HTTP REST              |
|                          | (Vite proxy:5173->8000)|
|  +-----------------------v----------------------+  |
|  |           FastAPI 后端 (Python)               |  |
|  |                                              |  |
|  |  Routers (6):                                |  |
|  |  /api/auth       JWT 认证                   |  |
|  |  /api/dicom      DICOM 管理                 |  |
|  |  /api/models     自定义模型管理               |  |
|  |  /api/segmentation  U-Net 分割              |  |
|  |  /api/igtv       IGTV 重建                  |  |
|  |  /api/trajectory LSTM 预测                  |  |
|  |                                              |  |
|  |  Services:                                   |  |
|  |  auth_service    加密 + JWT                  |  |
|  |  dicom_parser    pydicom 解析                |  |
|  |  inference       AI 推理引擎                 |  |
|  |                                              |  |
|  |  Models:                                     |  |
|  |  unet.py         Attention U-Net             |  |
|  |  lstm.py         BiLSTM + TCN                |  |
|  |  onnx_loader.py  ONNX/PyTorch 加载器         |  |
|  |  igtv_reconstruct.py  Marching Cubes        |  |
|  +-----------------------+----------------------+  |
|                          | SQLAlchemy            |
|  +-----------------------v----------------------+  |
|  |               MySQL 数据库                    |  |
|  |  users, patients, studies, series, slices,   |  |
|  |  segmentations, igtv_results, trajectories,  |  |
|  |  user_models, oauth_tokens                   |  |
|  +----------------------------------------------+  |
+====================================================+
```

---

## 数据模型关系

```
users (1) ----< user_models (用户上传的AI模型)
users (1) ----< oauth_tokens

patients (1) ----< studies (检查)
studies (1) ----< series (时相, phase 0-9)
series (1) ----< slices (单张CT切片)
slices (1) ---- segmentations (分割mask, 1:1)

studies (1) ---- igtv_results (IGTV重建, 1:1)
studies (1) ----< trajectories (运动轨迹, 每时相一条)

users.id = user_models.user_id
users.id = oauth_tokens.user_id
patients.id = studies.patient_id
studies.id = series.study_id
series.id = slices.series_id
slices.id = segmentations.slice_id
studies.id = igtv_results.study_id
studies.id = trajectories.study_id
```

---

## 核心数据流

### 1. 登录流程
```
客户端 POST /api/auth/login {username, password}
  -> auth_service.authenticate_user() 验证 bcrypt
  -> auth_service.create_access_token() 签发 JWT
  <- {access_token, username, role}
客户端存 token 到 localStorage
后续请求自动带 Authorization: Bearer <token>
```

### 2. DICOM 上传流程
```
客户端 POST /api/dicom/upload (multipart, 多个.dcm)
  -> dicom_parser.parse_dicom() 逐文件提取元数据
  -> 按 study_uid 分组
  -> 创建/查找 Patient
  -> 创建/查找 Study
  -> dicom_parser.group_slices_by_phase() 按 phase 分组
  -> 创建 Series (per phase) + Slice records
  -> 存储 DICOM 文件到 data/dicom/
  <- 返回上传统计
```

### 3. 自定义模型管理流程
```
上传:
  POST /api/models/upload (file + model_name + task_type)
  -> 验证扩展名(.pth/.onnx)
  -> 存储到 data/models/{user_id}/{uuid}.{ext}
  -> 写入 user_models 表

激活:
  PUT /api/models/{id}/activate
  -> 同任务类型其他模型 is_active = 0
  -> 目标模型 is_active = 1
  -> inference.load_custom_model() 加载到引擎内存

删除:
  DELETE /api/models/{id}
  -> 删除磁盘文件 + 数据库记录
```

### 4. AI 分割流程
```
POST /api/segmentation/run {study_id, model_id?}
  -> 获取 study 所有 slices
  -> 逐 slice 读取 DICOM -> 归一化
  -> inference.segment_slice() U-Net 推理
  -> 保存 mask (.npy) + 写入 segmentations 表
  <- {slices_processed, mean_dice}
```

### 5. IGTV 重建流程
```
POST /api/igtv/reconstruct {study_id}
  -> 加载所有 phase 的 segmentation masks
  -> igtv_reconstruct.fuse_phase_masks() union
  -> igtv_reconstruct.marching_cubes_mesh() 生成 3D mesh
  -> igtv_reconstruct.compute_igtv_volume() 计算体积
  -> 保存 ITV mask (.npy) + mesh (.obj) + 写入 igtv_results
  <- {volume_cc, mesh_path}
```

### 6. 轨迹预测流程
```
POST /api/trajectory/predict {study_id, model_id?}
  -> 收集每 phase 的 segmentation mask 质心
  -> 前 7 个 phase 作为观测值
  -> inference.predict_trajectory() LSTM 推理
  -> 存储 real + predicted 点位到 trajectories 表
  <- {observed_phases, predicted_phases}
```

---

## AI 模型模块详解

### Attention U-Net (`models/unet.py`)
```
输入: (B, 1, H, W) 单通道 CT 切片
架构:
  Encoder: ConvBlock x4 (64->128->256->512) + MaxPool
  Bottleneck: ConvBlock (1024)
  Decoder: UpConv x4 + AttentionGate x4 + skip connections
  Output: Conv2d(1) + Sigmoid -> 概率图
输出: (B, 1, H, W) binary mask
```

### Trajectory LSTM (`models/lstm.py`)
```
输入: (B, seq_len, 3) xyz centroid 序列
架构:
  Encoder: BiLSTM (bidirectional, 2 layers)
  Decoder: LSTM (2 layers, autoregressive)
  Output: Linear -> (B, pred_len, 3)
输出: (B, pred_len, 3) 预测 xyz

备选: SimpleTCN (更快的卷积替代方案)
```

### ONNX/PyTorch 加载器 (`models/onnx_loader.py`)
```
ONNXModel: ONNX Runtime InferenceSession
PyTorchModel: 先尝试 torch.jit.load, 失败则 state_dict
```

### IGTV 重建 (`models/igtv_reconstruct.py`)
```
fuse_phase_masks(): union (OR) / majority vote
marching_cubes_mesh(): skimage.measure.marching_cubes
  fallback: bounding box mesh
compute_igtv_volume(): voxel count * spacing -> cc
save_mesh_obj(): Wavefront OBJ 导出
```

### 推理引擎 (`services/inference.py`)
```
InferenceEngine (全局单例):
  - 管理分割/预测模型的加载状态
  - 支持内置模型 + 自定义 .pth/.onnx 模型
  - segment_slice(): 运行分割推理
  - predict_trajectory(): 运行轨迹预测
  - get_centroid(): 计算 mask 质心
```

---

## 前端数据流

```
Pinia Store (authStore)
  ├── token: localStorage.lungtic_token
  ├── user: {username, role}
  │
Axios Instance (api/index.ts)
  ├── baseURL: /api (Vite proxy to 127.0.0.1:8000)
  ├── Request interceptor: 自动注入 Bearer token
  └── Response interceptor: 401 -> 跳登录
```

---

## 安全设计

| 层级 | 措施 |
|------|------|
| 密码 | bcrypt 哈希, 不存明文 |
| 认证 | JWT HS256, 8小时过期 |
| API | 所有非 auth 路由需 get_current_user 依赖 |
| 文件上传 | 扩展名白名单(.pth/.onnx/.dcm) |
| CORS | 开发阶段 allow_origins=["*"] |
| Electron | contextIsolation: true, nodeIntegration: false |
