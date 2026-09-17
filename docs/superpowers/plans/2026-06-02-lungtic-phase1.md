# LungTic Phase 1 — 基础架构 + 登录 + 模型管理 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.
> Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** 搭建 LungTic 完整项目骨架：MySQL、FastAPI Auth、Electron + Vue (8pt Grid)、登录页、Dashboard、模型管理页。

**Architecture:** FastAPI + SQLAlchemy + MySQL；Electron + Vue 3 + Naive UI；JWT 认证；8pt Grid CSS 变量。

**Tech Stack:** Python 3.10+ / FastAPI / SQLAlchemy / PyJWT / MySQL 8.0 / Electron 30+ / Vue 3 / Vite / TypeScript / Naive UI

---

## 文件结构

 + "" + "" + "" + 
ui/
├── logo.jpg
├── database/schema.sql
├── backend/
│   ├── main.py, config.py, database.py, requirements.txt
│   ├── models/__init__.py, db_models.py
│   ├── routers/__init__.py, auth.py, models_router.py
│   └── services/__init__.py, auth_service.py
├── frontend/
│   ├── electron/main.js, preload.js
│   ├── index.html, package.json, vite.config.ts, tsconfig.json
│   └── src/
│       ├── main.ts, App.vue, env.d.ts
│       ├── router/index.ts, api/index.ts, stores/auth.ts
│       ├── styles/grid.css
│       ├── views/LoginPage.vue, DashboardLayout.vue, ModelManager.vue
│       └── components/ModelUpload.vue, ModelCard.vue
└── README.md
 + "" + "" + "" + 

---

### Task 1: MySQL Schema (ui/database/schema.sql)

创建完整建表语句（10 张表：users, patients, studies, series, slices, segmentations, igtv_results, trajectories, user_models, oauth_tokens），包含初始 admin 账号。

**验证:** 检查文件存在

---

### Task 2: FastAPI 骨架

- ui/backend/requirements.txt — fastapi, uvicorn, sqlalchemy, pymysql, pyjwt, passlib, python-multipart, pydantic
- ui/backend/config.py — DATABASE_URL, JWT_SECRET, UPLOAD_DIR, MODEL_DIR, DICOM_DIR
- ui/backend/database.py — engine, SessionLocal, Base, get_db()
- ui/backend/main.py — FastAPI app + CORS + health endpoint

**验证:** python main.py 启动成功，/api/health 返回 {"status":"ok"}

---

### Task 3: ORM 模型 (ui/backend/models/db_models.py)

所有表的 SQLAlchemy 映射：User, Patient, Study, Series, Slice, Segmentation, IgtvResult, Trajectory, UserModel, OAuthToken。含 Enum 类型定义。

---

### Task 4: Auth 服务 + API

- ui/backend/services/auth_service.py — hash_password, verify_password, create_access_token, decode_token, authenticate_user
- ui/backend/routers/auth.py — POST /api/auth/login, GET /api/auth/me
- 更新 main.py 注册 auth_router

**验证:** curl -X POST http://localhost:8000/api/auth/login -d '{"username":"admin","password":"admin123"}' 返回 JWT token

---

### Task 5: 模型管理 API

- ui/backend/routers/models_router.py — POST /api/models/upload, GET /api/models/, PUT /api/models/{id}/activate, DELETE /api/models/{id}
- 支持 .pth / .onnx，同一任务类型只能激活一个模型
- 更新 main.py 注册 models_router

**验证:** 上传 .pth 文件 → 列表出现 → 激活 → 删除

---

### Task 6: Electron + Vue 脚手架

- ui/frontend/package.json — vue, vue-router, pinia, axios, naive-ui, electron, vite, typescript
- ui/frontend/index.html — 入口 HTML
- ui/frontend/vite.config.ts — alias @, proxy /api → 127.0.0.1:8000
- ui/frontend/tsconfig.json + 	sconfig.node.json
- ui/frontend/electron/main.js — BrowserWindow 1400x900
- ui/frontend/electron/preload.js — contextBridge
- ui/frontend/src/main.ts — createApp + pinia + router + grid.css
- ui/frontend/src/App.vue — <router-view />
- ui/frontend/src/env.d.ts — Vue 类型声明

**验证:** 
pm install 无错误，
pm run dev 启动

---

### Task 7: 8pt Grid CSS (ui/frontend/src/styles/grid.css)

CSS 变量系统：
- 间距: --space-xs(4px) ~ --space-3xl(64px)，均为 8 的倍数
- 圆角: --radius-sm(4px), --radius-md(8px), --radius-lg(16px)
- 字号: --text-xs(12px) ~ --text-xl(24px)
- 品牌色: --color-primary(#1E88E5), --color-bg(#F5F7FA), --color-sidebar(#1E293B)
- 侧边栏: --sidebar-width(256px = 32*8)
- 全局 reset: margin/padding 归零, border-box, 中文字体栈

---

### Task 8: 路由 + API 封装 + Auth Store

- ui/frontend/src/router/index.ts — hash 路由: /login, /dashboard (含 beforeEach 鉴权)
- ui/frontend/src/api/index.ts — axios 实例, baseURL /api, 自动注入 Bearer token, 401 跳登录
- ui/frontend/src/stores/auth.ts — Pinia store: login(), fetchMe(), logout()

---

### Task 9: 登录页 (ui/frontend/src/views/LoginPage.vue)

- 居中卡片: logo.jpg + LungTic 标题 + 副标题
- Naive UI 表单: 用户名 + 密码 (支持回车登录)
- 错误提示
- 渐变色背景 (primary → primary-dark)

**验证:** 输入 admin/admin123 → 跳转 Dashboard

---

### Task 10: Dashboard 布局 (ui/frontend/src/views/DashboardLayout.vue)

- 左侧深色侧边栏 (256px): Logo + 菜单项「模型管理」+ 折叠按钮
- 顶部栏: 页面标题 + 用户名标签 + 退出按钮
- 内容区: <router-view /> 白色背景 card 风格
- onMounted 调用 fetchMe() 获取用户信息

---

### Task 11: 模型管理页面

- ui/frontend/src/components/ModelUpload.vue — Naive UI Upload 拖拽组件 (.pth/.onnx), 模型名称输入, 任务类型下拉, 确认上传
- ui/frontend/src/components/ModelCard.vue — 卡片: 模型名/格式/任务/激活状态/激活按钮/删除按钮
- ui/frontend/src/views/ModelManager.vue — 上传区 + 模型卡片网格 (280px 卡片宽度, gap 16px)

**验证:** 上传模型 → 列表刷新 → 激活 → 删除

---

### Task 12: 端到端验证

1. 启动 MySQL → 导入 schema.sql
2. cd backend && python main.py
3. cd frontend && npm run dev
4. 浏览器: 登录 → Dashboard → 模型管理 → 上传/激活/删除

---

## 完成标准

- [ ] MySQL 10 张表创建成功
- [ ] FastAPI health + auth + models API 正常
- [ ] Electron + Vue 编译通过
- [ ] 8pt Grid 样式正确
- [ ] 登录 → Dashboard → 模型管理 全流程跑通
