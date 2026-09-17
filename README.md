# LungTic — 基于 U-Net 的 4D 肺癌诊断与预测

## 中心病例服务

私有分支 `feat/clinical-records-server` 增加病例附件上传、科室与诊疗团队权限、限时会诊授权和访问审计。数据库迁移、密钥配置、管理员初始化及验证步骤见 [中心病例服务运行说明](docs/CLINICAL_SERVER.md)。中心服务启动时必须显式配置数据库 URL、JWT/验证码密钥及前端来源。

```powershell
cd backend
pip install -r requirements.txt
python bootstrap_admin.py
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

```powershell
cd frontend
npm install
npm run dev
```

## TICI 查看器

使用医生或管理员账户登录后，从左侧进入“**TICI 查看器**”，或访问
`/dashboard/tici-viewer`。查看器可直接打开 `.tici` 文件，不会把文件导入患者数据库。

功能包括多时相切换、轴位逐层浏览、时相播放、缩放、自动/手动调窗、Mask
叠加和元数据检查。可使用方向键切层、`PageUp/PageDown` 切换时相、空格键播放或暂停。

示例文件位于：

```text
../model_training/examples/tici_demo/output/example4d.tici
```

扩展边界和接口说明见 [`docs/TICI_VIEWER.md`](docs/TICI_VIEWER.md)。

## Windows EXE 打包

独立查看器安装包会同时封装 Electron 前端和精简的本地 FastAPI 后端，运行时使用
本机 SQLite，不要求安装 MySQL。首次启动账号为 `admin`，密码为 `admin123`；登录后
请从左侧“设置”修改默认密码。

```powershell
cd frontend
npm run package:viewer
```

默认使用 `D:\envs\lungtic-training\python.exe` 构建 Python sidecar。安装包输出在
`frontend/release`。
