# LungTic Windows 快速启动

本指南用于本地合成数据开发。生产部署请阅读 [`docs/CLINICAL_SERVER.md`](docs/CLINICAL_SERVER.md) 和 [`HANDOFF.md`](HANDOFF.md)。

## 1. 准备环境

- Python 3.10–3.12
- Node.js 18+、npm 9+
- Git
- 生产或多人环境另需 MySQL 8.0+

## 2. 启动后端

在 `web_source` 目录打开 PowerShell：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

New-Item -ItemType Directory -Force .local-data | Out-Null
$dbPath = (Join-Path $PWD 'lungtic-dev.sqlite').Replace('\', '/')
$env:LUNGTIC_DB_URL = "sqlite:///$dbPath"
$env:LUNGTIC_DATA_DIR = (Join-Path $PWD '.local-data')
$env:LUNGTIC_CORS_ORIGINS = 'http://127.0.0.1:5173,http://127.0.0.1:5174,app://lungtic'
$env:LUNGTIC_JWT_SECRET = python -c "import secrets; print(secrets.token_urlsafe(48))"
$env:LUNGTIC_CAPTCHA_SECRET = python -c "import secrets; print(secrets.token_urlsafe(48))"
$recordKey = python -c "import base64,secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())"
$env:LUNGTIC_RECORD_ACTIVE_KEY_ID = 'v1'
$env:LUNGTIC_RECORD_KEYS_JSON = '{"v1":"' + $recordKey + '"}'

python -c "from database import Base, engine; import models.db_models; Base.metadata.create_all(engine)"
$env:LUNGTIC_BOOTSTRAP_USERNAME = 'admin'
$env:LUNGTIC_BOOTSTRAP_PASSWORD = Read-Host '输入至少 12 位管理员密码'
python bootstrap_admin.py
Remove-Item Env:LUNGTIC_BOOTSTRAP_PASSWORD

python -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1
```

浏览器访问 `http://127.0.0.1:8000/api/health`，应看到 `{"status":"ok","app":"LungTic"}`。不要关闭这个后端终端。

## 3. 启动前端

临床客户端开发页：

```powershell
cd frontend
npm ci
npm run dev
```

访问 `http://127.0.0.1:5173`。

管理后台使用另一个终端：

```powershell
cd frontend
npm run dev:admin
```

访问 `http://127.0.0.1:5174`。

## 4. 一键启动

完成依赖安装并在当前 PowerShell 设置好后端环境变量后，可从 `web_source` 运行：

```powershell
.\start-all.cmd
```

它会分别打开 API、临床客户端和管理后台窗口。

## 5. 常见问题

- 后端启动时报缺少环境变量：按第 2 步在同一个 PowerShell 设置变量后再启动。
- 5173 和 5174 显示相同页面：结束旧 Vite 进程，确认 5174 使用 `npm run dev:admin`。
- 验证码加载失败：先检查 `/api/health`，再看前端代理和 HTTPS 证书是否正常。
- 数据库连接失败：检查 `LUNGTIC_DB_URL`，不要在源码中写真实密码。
- 内存占用过高：保持 Uvicorn 单 worker，CPU 服务器安装 CPU 版 PyTorch，并检查是否误启动了多份后端。
- 桌面客户端连接失败：检查服务域名证书链、主机名和公钥 SHA-256 固定值是否一致。

单机 TICI 查看器的本地初始账号仅用于离线查看器，不能作为中央服务管理员账号。首次登录后应立即修改。
