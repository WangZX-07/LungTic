# LungTic 项目总结 — 完整开发状态

> 日期: 2026-06-02 | 版本: Phase 1 完成 + AI 管线完整实现

---

## 1. 项目概述

**LungTic** 是"基于 U-Net 的 4D 肺癌诊断与预测"竞赛项目的桌面端可视化系统。核心功能：
- 4D CT DICOM 影像上传与解析
- 用户自定义 AI 模型(.pth/.onnx)管理
- Attention U-Net 肿瘤分割
- IGTV 三维靶区重建
- LSTM 肿瘤运动轨迹预测

---

## 2. 技术栈

| 层级 | 技术 |
|------|------|
| 桌面壳 | Electron 30+ |
| 前端框架 | Vue 3 + Vite 5 + TypeScript |
| UI 组件库 | Naive UI 2.39 |
| 图标 | @vicons/ionicons5 |
| 状态管理 | Pinia 2 |
| HTTP 客户端 | Axios |
| 后端 | FastAPI (Python 3.10+) |
| ORM | SQLAlchemy 2.0 |
| 数据库 | MySQL 8.0 |
| 认证 | JWT (bcrypt + PyJWT) |
| AI 框架 | PyTorch 2.x + ONNX Runtime |
| DICOM 解析 | pydicom + scikit-image |
| 设计系统 | 8pt Grid |

---

## 3. 已完成功能清单

### 后端 (FastAPI)

| 模块 | 文件 | 功能 |
|------|------|------|
| 配置 | `backend/config.py` | DB URL, JWT 密钥, 文件目录 |
| 数据库 | `backend/database.py` | SQLAlchemy engine + session |
| 入口 | `backend/main.py` | FastAPI app, CORS, 6个路由注册 |
| ORM 模型 | `backend/models/db_models.py` | 10 张表映射 (User/Patient/Study/Series/Slice/Segmentation/IgtvResult/Trajectory/UserModel/OAuthToken) |
| U-Net 模型 | `backend/models/unet.py` | Attention U-Net (encoder-decoder + attention gate + skip connection) |
| LSTM 模型 | `backend/models/lstm.py` | BiLSTM + TCN 轨迹预测 |
| ONNX 加载器 | `backend/models/onnx_loader.py` | ONNX Runtime + PyTorch(TorchScript/state_dict) 双加载器 |
| IGTV 重建 | `backend/models/igtv_reconstruct.py` | Marching Cubes + OBJ 导出 + 体积计算 |
| 认证服务 | `backend/services/auth_service.py` | bcrypt + JWT 签发/验证 |
| DICOM 解析 | `backend/services/dicom_parser.py` | pydicom 元数据提取 + 按相位分组 |
| 推理引擎 | `backend/services/inference.py` | 统一推理引擎: 内置/自定义模型加载, 分割/预测 |
| Auth API | `backend/routers/auth.py` | POST /api/auth/login, GET /api/auth/me |
| DICOM API | `backend/routers/dicom.py` | 上传/患者列表/检查/序列/切片/图片 base64 |
| 分割 API | `backend/routers/segmentation.py` | POST /api/segmentation/run, GET result |
| IGTV API | `backend/routers/igtv.py` | POST /api/igtv/reconstruct, GET result |
| 轨迹 API | `backend/routers/trajectory.py` | POST /api/trajectory/predict, GET result |
| 模型管理 API | `backend/routers/models_router.py` | POST upload, GET list, PUT activate, DELETE |

### 前端 (Vue 3 + Electron)

| 模块 | 文件 | 功能 |
|------|------|------|
| Electron 壳 | `frontend/electron/main.js` | BrowserWindow 1400x900 |
| 路由 | `frontend/src/router/index.ts` | hash 模式 + beforeEach JWT 鉴权 |
| API 封装 | `frontend/src/api/index.ts` | axios 实例, Bearer Token 自动注入 |
| Auth Store | `frontend/src/stores/auth.ts` | Pinia: login/fetchMe/logout |
| 8pt Grid | `frontend/src/styles/grid.css` | CSS 变量: 间距/圆角/字号/品牌色 |
| 登录页 | `frontend/src/views/LoginPage.vue` | Logo + 表单 + 渐变背景 |
| Dashboard | `frontend/src/views/DashboardLayout.vue` | 深色侧边栏 + 顶栏 + 内容区 |
| 患者列表 | `frontend/src/views/PatientList.vue` | DICOM 上传 + 患者表格 + 检查查看 |
| 研究工作区 | `frontend/src/views/StudyWorkspace.vue` | 三 Tab: 横断面/3D靶区/运动轨迹 |
| 模型管理 | `frontend/src/views/ModelManager.vue` | 上传区 + 模型卡片网格 |
| 模型上传 | `frontend/src/components/ModelUpload.vue` | 拖拽上传 + 名称/任务选择 |
| 模型卡片 | `frontend/src/components/ModelCard.vue` | 激活/停用/删除 |
| 横断面视图 | `frontend/src/components/AxialView.vue` | CT 图像 + mask 叠加 + 相位/层数滑块 |
| 3D 靶区 | `frontend/src/components/Target3DView.vue` | IGTV 重建 + 体积显示 (Three.js 占位) |
| 轨迹视图 | `frontend/src/components/TrajectoryView.vue` | LSTM 预测 + 图表 (ECharts 占位) |

### 数据库

| 文件 | 内容 |
|------|------|
| `database/schema.sql` | 10 表建表语句 + admin 初始账号 |

---

## 4. 项目文件树

```
ui/
├── logo.jpg
├── README.md
├── database/
│   └── schema.sql
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── requirements.txt
│   ├── models/
│   │   ├── __init__.py
│   │   ├── db_models.py
│   │   ├── unet.py
│   │   ├── lstm.py
│   │   ├── onnx_loader.py
│   │   └── igtv_reconstruct.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── dicom.py
│   │   ├── models_router.py
│   │   ├── segmentation.py
│   │   ├── igtv.py
│   │   └── trajectory.py
│   └── services/
│       ├── __init__.py
│       ├── auth_service.py
│       ├── dicom_parser.py
│       └── inference.py
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   ├── electron/
│   │   ├── main.js
│   │   └── preload.js
│   └── src/
│       ├── main.ts
│       ├── App.vue
│       ├── env.d.ts
│       ├── router/index.ts
│       ├── api/index.ts
│       ├── stores/auth.ts
│       ├── styles/grid.css
│       ├── views/
│       │   ├── LoginPage.vue
│       │   ├── DashboardLayout.vue
│       │   ├── PatientList.vue
│       │   ├── StudyWorkspace.vue
│       │   └── ModelManager.vue
│       └── components/
│           ├── ModelUpload.vue
│           ├── ModelCard.vue
│           ├── AxialView.vue
│           ├── Target3DView.vue
│           └── TrajectoryView.vue
└── docs/superpowers/
    ├── specs/2026-06-02-4d-lung-cancer-ui-design.md
    └── plans/2026-06-02-lungtic-phase1.md
```

---

## 5. 待完成/待集成

| 项目 | 说明 |
|------|------|
| Cornerstone.js | DICOM Canvas 渲染 (目前用 base64 PNG 替代) |
| Three.js | IGTV 3D 可视化 (目前仅占位) |
| ECharts | 运动轨迹曲线图 (目前仅占位) |
| Cornerstone3D | MPR 多平面重建 |
| WebSocket | AI 推理进度推送 |
| 前端 E2E 测试 | Playwright |
| 模型训练 | 内置模型权重训练 |
| OAuth | 预留接口未实现 |
| Electron 打包 | electron-builder 配置 |

---

## 6. 关键设计决策

- **8pt Grid**: 所有间距基于 4/8/16/24/32/48/64px
- **路由模式**: hash (Electron 兼容)
- **API 代理**: Vite dev proxy /api -> 127.0.0.1:8000
- **品牌色**: #1E88E5 (primary), #1E293B (sidebar)
- **认证**: JWT + localStorage, 路由 beforeEach 鉴权
- **模型管理**: 同一任务类型只能激活一个模型
- **默认账号**: admin / admin123

---

## 7. 启动命令

```bash
# 数据库
mysql -u root -p < database/schema.sql

# 后端
cd backend && pip install -r requirements.txt && python main.py

# 前端 (浏览器)
cd frontend && npm install && npm run dev

# 前端 (Electron)
cd frontend && npm run electron:dev
```
