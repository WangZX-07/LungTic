# LungTic Web Source

本目录是 LungTic 项目的完整交付根目录，包含临床桌面客户端、浏览器管理后台、FastAPI 中心服务、数据库脚本、TICI 工具和项目文档。

## 组成

| 模块 | 目录 | 说明 |
|---|---|---|
| 中心服务 | `backend/` | FastAPI、权限控制、病例加密、审计、通知、SMTP 配置与 AI/影像接口 |
| 临床客户端与管理后台 | `frontend/` | Vue 3；Electron 桌面客户端和独立浏览器管理后台 |
| 数据库 | `database/` | MySQL 全量建库脚本和增量迁移 |
| TICI 工具 | `tici/` | `.tici` 文件读写与转换 |
| 设计与部署文档 | `docs/` | 客户端/后台拆分、服务部署、专利和设计资料 |
| Windows 构建产物 | `backend-dist/`、`build/` | 本地生成目录，已被 Git 忽略 |

更完整的维护信息见 [HANDOFF.md](HANDOFF.md)，逐项材料说明见 [MATERIALS.md](MATERIALS.md)。

## 环境要求

- Python 3.10–3.12（生产环境不建议使用实验性 Python/Numpy 组合）
- Node.js 18+ 和 npm 9+
- MySQL 8.0+（生产/多人环境）；SQLite 仅用于本地合成数据开发
- Windows 10/11（打包 Electron 安装包）；服务端可部署在 Linux

## 本地开发

以下命令从 `web_source` 目录执行。只使用合成数据或充分去标识化数据。

### 1. 后端

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

健康检查：`http://127.0.0.1:8000/api/health`。中央服务不会创建默认管理员密码；后续若需轮换管理员密码，重新设置临时的 `LUNGTIC_BOOTSTRAP_PASSWORD` 并执行 `bootstrap_admin.py`。

### 2. 临床客户端与管理后台

```powershell
cd ..\frontend
npm ci
npm run dev
```

临床客户端开发页为 `http://127.0.0.1:5173`。管理后台使用另一个终端启动：

```powershell
cd frontend
npm run dev:admin
```

管理后台开发页为 `http://127.0.0.1:5174`。两个端口呈现不同入口；若两者看起来相同，应确认使用了 `npm run dev:admin`，并清理旧的 Vite 进程。

## MySQL 初始化与迁移

全新数据库直接执行：

```bash
mysql -u <管理账号> -p < database/schema.sql
```

旧数据库按顺序执行（执行前先备份）：

```text
database/migrations/phase2.sql
database/migrations/phase2b.sql
database/migrations/phase3.sql
database/migrations/phase4_record_encryption.sql
database/migrations/phase5_internal_notifications.sql
database/migrations/phase6_smtp_settings.sql
```

生产连接通过 `LUNGTIC_DB_URL` 注入，例如 `mysql+pymysql://USER:PASSWORD@127.0.0.1:3306/lungtic`。真实密码只写入服务器的受限环境文件，不写入源码、命令历史或安装包。

## 构建与测试

```powershell
cd frontend
npm run build
npm run build:admin
node --test electron/connection.test.js

cd ..\backend
python -m pytest tests -q
```

打包命令：

```powershell
cd frontend
npm run package:client
npm run package:viewer
```

服务器打包脚本位于 `backend/scripts/package-server.ps1`。生成目录不提交 Git。

## 部署入口

- 中心服务部署：[docs/CLINICAL_SERVER.md](docs/CLINICAL_SERVER.md)
- 客户端与管理后台拆分：[docs/CLIENT_ADMIN_SPLIT.md](docs/CLIENT_ADMIN_SPLIT.md)
- TICI 查看器：[docs/TICI_VIEWER.md](docs/TICI_VIEWER.md)
- 当前生产域名：临床 API `https://clinical.respulse.top`，管理后台 `https://admin.respulse.top`

桌面客户端内置 HTTPS 地址和服务器公钥 SHA-256 固定值。TLS 公钥发生变化时，必须重新计算固定值并发布客户端更新，或在客户端设置中重新配置。不要把服务器私钥或共享 API 密钥打进客户端。

## 数据安全边界

- 病例附件使用 AES-256-GCM 认证加密，并记录明文与密文 SHA-256 校验值。
- 密钥环由 `LUNGTIC_RECORD_ACTIVE_KEY_ID` 和 `LUNGTIC_RECORD_KEYS_JSON` 提供；密钥不得进入仓库。
- 医生、患者、科主任和管理员权限由服务端强制执行，前端隐藏按钮不是权限控制。
- 病例访问、上传、下载、授权和管理操作写入审计事件。
- SMTP 密码由病例主密钥派生的独立密钥加密保存。
- 真实病例、数据库、备份、模型权重、证书私钥与 `.env` 文件均被忽略，仍需在提交前人工复核。
