# LungTic 项目交接文档

更新时间：2026-11-10
维护分支：`feat/clinical-records-server`

## 1. 交付范围

本交付包含三个面向不同使用者的入口：

1. 临床桌面客户端：仅医生和患者登录，Electron 封装，内置生产 API 地址与 TLS 公钥固定值。
2. 浏览器管理后台：管理员独立登录，用于组织、用户、审计和 SMTP 配置。
3. 中心服务：FastAPI + SQLAlchemy，负责认证、权限、病例、影像、通知、审计和加密存储。

另包含单机 TICI 查看器、`.tici` 工具、数据库脚本、设计说明和专利材料。

## 2. 运行架构

```text
医生/患者 Electron 客户端 ── HTTPS + 公钥固定 ─┐
                                                  ├─ Nginx ─ FastAPI ─ MySQL
管理员浏览器后台 ─────────── HTTPS ─────────────┘                │
                                                                    └─ 受控病例文件目录
```

推荐将 API 仅监听 `127.0.0.1:8000`，由 Nginx 暴露 HTTPS。管理后台为静态文件，由独立域名托管并将 `/api` 反代到 API。服务端生产进程使用单 worker 起步，避免模型与影像库在多进程中重复占用内存。

## 3. 权限模型

| 身份 | 可见范围 | 写入范围 |
|---|---|---|
| 患者 | 自己的患者档案，以及医生明确设为患者可见的资料 | 无病例写权限 |
| 医生 | 本人责任患者、有效临时授权患者；科主任额外可读本科室患者 | 本人责任患者或带写权限的有效授权患者 |
| 科主任 | 医生权限 + 本科室患者只读范围 | 不因主任身份自动获得写权限 |
| 管理员 | 管理组织、用户、授权、审计与 SMTP | 不通过临床客户端直接读取病例内容 |

直接按 ID 访问与列表查询共用服务端权限策略；无权资源返回 404，减少资源枚举。所有允许和拒绝事件均写入 `audit_events`。

## 4. 病例安全

- 上传白名单：PDF、PNG、JPEG、TICI、DICOM，并校验扩展名与文件头。
- 单文件上限：512 MB；流式分块处理，避免把整个文件读入内存。
- 每个文件使用独立数据密钥执行 AES-256-GCM；数据密钥由版本化主密钥包装。
- 保存明文 SHA-256 与密文 SHA-256；读取前验证完整性。
- 主密钥只来自进程环境，不落入数据库或 Git。
- 轮换时新增 key ID，并用 `rewrap_record_keys.py` 重包数据密钥；旧密钥在确认全部重包和备份可恢复前不得删除。
- SMTP 密码使用 HKDF 从主密钥派生独立设置密钥，再以 AES-GCM 加密。

生产环境还需补齐：医院统一身份、终端撤销、恶意文件扫描、上传限流、审计防篡改、备份恢复演练和独立安全测试。首次试运行只使用合成或充分去标识化数据。

## 5. 数据库

全新部署使用 `database/schema.sql`。旧库依次执行：

1. `phase2.sql`
2. `phase2b.sql`
3. `phase3.sql`
4. `phase4_record_encryption.sql`
5. `phase5_internal_notifications.sql`
6. `phase6_smtp_settings.sql`

执行前备份，执行后检查 `departments`、`department_memberships`、`patient_care_assignments`、`access_grants`、`clinical_records`、`audit_events`、`notifications` 和 `smtp_settings`。中央服务管理员使用 `backend/bootstrap_admin.py` 创建，不存在生产默认密码。

## 6. 生产环境变量

必须配置：

- `LUNGTIC_DB_URL`
- `LUNGTIC_DATA_DIR`
- `LUNGTIC_JWT_SECRET`（至少 32 字符）
- `LUNGTIC_CAPTCHA_SECRET`（至少 32 字符且与 JWT 不同）
- `LUNGTIC_CORS_ORIGINS`（明确列出来源，不使用 `*`）
- `LUNGTIC_RECORD_ACTIVE_KEY_ID`
- `LUNGTIC_RECORD_KEYS_JSON`（每把密钥为 32 随机字节的 Base64）

机密应放入权限为 `0600` 的服务环境文件或密钥管理系统。不要把值复制到工单、聊天、截图、仓库或客户端。示例见 `backend/scripts/server.env.example.ps1`。

## 7. TLS 与客户端固定值

客户端同时要求证书链有效、主机名匹配和公钥 SHA-256 固定值匹配。计算命令：

```powershell
cd frontend
node scripts/show-server-pin.js C:\path\to\fullchain-or-cert.pem
```

证书续期若复用了同一私钥，公钥固定值通常不变；更换私钥后固定值必然变化。变更前应先发布接受新固定值的客户端，避免全部终端断连。服务器私钥永远不能分发到客户端。

## 8. 构建、验证与资源控制

交付前至少运行：

```powershell
cd backend
python -m pytest tests -q

cd ..\frontend
npm run build
npm run build:admin
node --test electron/connection.test.js
```

资源注意事项：

- Uvicorn 默认 `--workers 1`；确认内存稳定后再评估横向扩容。
- CPU 服务器使用 CPU 版 PyTorch，避免安装无用 CUDA 运行时。
- 病例上传采用固定大小分块；不要改为一次性 `read()`。
- 通知轮询和影像播放组件应在页面卸载时清理定时器。
- 生产机持续观察 `systemctl status lungtic`、`journalctl -u lungtic`、RSS、磁盘和文件句柄。

## 9. 已知边界与后续事项

- Windows 安装包尚需机构代码签名证书。
- 生产域名、Nginx、证书和 systemd 配置保存在服务器，不在仓库中提交真实密钥。
- 公钥固定值在服务器更换 TLS 私钥后需要同步更新。
- 管理后台和临床客户端均需继续做真实移动端/终端兼容性验收。
- AI 模型推理的性能、准确性和医疗合规性必须单独验证，本项目代码不能替代医疗器械注册与临床验证。

## 10. 接手检查清单

- [ ] 从干净环境安装依赖并通过全部测试
- [ ] 使用合成数据验证医生、患者、科主任和管理员权限
- [ ] 验证无权直接 ID 访问返回 404，审计事件完整
- [ ] 验证病例加密上传、下载、篡改检测和密钥轮换
- [ ] 验证内部信箱通知与 SMTP 密码重置
- [ ] 检查 Nginx HTTPS、HSTS、CSP、请求体上限与超时
- [ ] 检查数据库和病例目录备份、权限与恢复演练
- [ ] 重新计算并核对客户端 TLS 公钥固定值
- [ ] 在干净 Windows 终端验收安装、登录、升级和卸载
