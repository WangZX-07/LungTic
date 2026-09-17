# LungTic 前端 UI 组件树 & 状态文档

> 用于新对话框 UI 设计时快速了解现有前端结构

---

## 路由结构

```
/                          -> redirect /login
/login                     -> LoginPage.vue
/dashboard                 -> DashboardLayout.vue (父布局)
  /dashboard/patients      -> PatientList.vue
  /dashboard/models        -> ModelManager.vue
  /dashboard/study/:id     -> StudyWorkspace.vue
```

**鉴权**: `router.beforeEach` 检查 `localStorage.lungtic_token`，无 token 跳转 `/login`。

---

## 组件树

```
App.vue
├── LoginPage.vue                          # 一级界面：登录
│
└── DashboardLayout.vue                    # 二级界面：主布局
    ├── 顶部栏 (.topbar)
    │   ├── 页面标题
    │   ├── NTag (用户名)
    │   └── NButton (退出)
    │
    ├── 侧边栏 (.sidebar) — 256px 深色
    │   ├── logo.jpg + "LungTic"
    │   ├── NMenu:
    │   │   ├── "患者列表" -> /dashboard/patients
    │   │   └── "模型管理" -> /dashboard/models
    │   └── 折叠按钮
    │
    └── 内容区 (.content)
        ├── PatientList.vue                # 患者列表
        │   ├── NUpload (DICOM 上传按钮)
        │   ├── NDataTable (患者表格)
        │   ├── NModal (检查记录弹窗)
        │   └── 跳转 StudyWorkspace
        │
        ├── ModelManager.vue               # 模型管理
        │   ├── ModelUpload.vue            # 上传卡片
        │   │   ├── NUploadDragger (.pth/.onnx 拖拽区)
        │   │   ├── NInput (模型名称)
        │   │   ├── NSelect (任务类型: 分割/预测)
        │   │   └── NButton (确认上传)
        │   └── ModelCard.vue (v-for grid) # 模型卡片
        │       ├── NTag (激活状态)
        │       ├── 格式/任务信息
        │       ├── NButton (激活/停用)
        │       └── NPopconfirm + NButton (删除)
        │
        └── StudyWorkspace.vue             # 研究工作区
            ├── NTabs (3 tabs):
            │   ├── "横断面视图" -> AxialView.vue
            │   │   ├── 左侧: CT 图像 + mask 叠加 (.canvas-area)
            │   │   └── 右侧控制面板:
            │   │       ├── NSlider (时相 0-9)
            │   │       ├── NSlider (层数)
            │   │       ├── 分割信息 (Dice/模型版本)
            │   │       └── NCheckbox (显示 Mask 叠加)
            │   │
            │   ├── "3D 靶区视图" -> Target3DView.vue
            │   │   ├── 左侧: Three.js 容器 (.threejs-container, 占位)
            │   │   ├── 右侧: IGTV 体积信息
            │   │   ├── NButton (重建 IGTV)
            │   │   └── 旋转控制按钮组
            │   │
            │   └── "运动轨迹" -> TrajectoryView.vue
            │       ├── ECharts 图表区 (.chart-area, 占位)
            │       ├── NSwitch (显示预测)
            │       └── NButton (预测轨迹)
            │
            └── 顶部操作栏
                ├── 返回按钮
                ├── Study 标签
                └── 执行分割按钮
```

---

## Store 状态

### authStore (Pinia: `useAuthStore`)

```typescript
{
  user: { username: string, role: string } | null,
  token: string,
  login(username, password) -> Promise,
  fetchMe() -> Promise,
  logout() -> void
}
```

---

## API 接口清单

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 登录 |
| GET | `/api/auth/me` | 当前用户信息 |
| POST | `/api/dicom/upload` | 上传 DICOM 文件 |
| GET | `/api/dicom/patients` | 患者列表 |
| GET | `/api/dicom/patients/:id` | 患者详情 |
| GET | `/api/dicom/patients/:id/studies` | 患者检查列表 |
| GET | `/api/dicom/studies/:id/phases` | 检查时相列表 |
| GET | `/api/dicom/series/:id/slices` | 序列切片列表 |
| GET | `/api/dicom/slice/:id/image` | 切片 base64 图像 |
| POST | `/api/models/upload` | 上传自定义模型 |
| GET | `/api/models/` | 模型列表 |
| PUT | `/api/models/:id/activate` | 激活模型 |
| DELETE | `/api/models/:id` | 删除模型 |
| POST | `/api/segmentation/run` | 执行分割 |
| GET | `/api/segmentation/:studyId/result` | 分割结果 |
| POST | `/api/igtv/reconstruct` | IGTV 重建 |
| GET | `/api/igtv/:studyId` | IGTV 结果 |
| POST | `/api/trajectory/predict` | 轨迹预测 |
| GET | `/api/trajectory/:studyId` | 轨迹数据 |
| GET | `/api/health` | 健康检查 |

---

## 8pt Grid CSS 变量

定义在 `frontend/src/styles/grid.css`:

```css
--space-xs: 4px
--space-sm: 8px
--space-md: 16px
--space-lg: 24px
--space-xl: 32px
--space-2xl: 48px
--space-3xl: 64px
--radius-sm: 4px
--radius-md: 8px
--radius-lg: 16px
--text-xs: 12px ~ --text-xl: 24px
--color-primary: #1E88E5
--color-primary-dark: #1565C0
--color-primary-light: #42A5F5
--color-bg: #F5F7FA
--color-sidebar: #1E293B
--color-text: #1E293B
--color-text-secondary: #64748B
--color-border: #E2E8F0
--color-success: #22C55E
--color-danger: #EF4444
--color-warning: #F59E0B
--sidebar-width: 256px
```

---

## 关键布局尺寸

| 元素 | 尺寸 |
|------|------|
| 侧边栏宽度 | 256px (32×8) |
| 侧边栏折叠宽度 | 64px |
| 顶栏高度 | 56px |
| 登录卡片宽度 | 400px |
| 登录卡片内边距 | 48px |
| 内容区内边距 | 24px |
| 模型卡片宽度 | 280px |
| 模型卡片间距 | 16px |
| 患者列表最大宽度 | 960px |
| Logo (sidebar) | 32×32px |
| Logo (login) | 80×80px |

---

## 待集成的外部库

| 库 | 用途 | 当前状态 |
|----|------|----------|
| Cornerstone.js | DICOM Canvas 渲染 | 未集成 (用 base64 PNG 替代) |
| Three.js | IGTV 3D 可视化 | 未集成 (占位符) |
| ECharts | 运动轨迹图表 | 未集成 (占位符) |
| Cornerstone3D | MPR 多平面重建 | 未集成 |

---

## 当前 UI 问题 / 待优化

1. AxialView 的 mask 叠加图片是占位逻辑，需要真实渲染
2. Target3DView 的 Three.js 未集成，只有静态占位符
3. TrajectoryView 的 ECharts 未集成，只有静态占位符
4. 所有中文文本在部分文件中有编码问题
5. login 页目前硬编码跳转 /dashboard，缺少多角色处理
6. PatientList 每次只上传一个文件，但使用 multiple 属性
7. 侧边栏菜单不支持子路由高亮 (study/:id 时患者列表不高亮)
