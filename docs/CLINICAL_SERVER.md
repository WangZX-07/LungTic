# 中心病例服务：运行与权限

本分支提供 FastAPI + MySQL 的病例服务 MVP。使用合成数据验证；上线处理真实病例前，仍需完成医院内网部署、安全评估、备份恢复和数据治理流程。医生/患者桌面客户端、浏览器管理后台和中心 API 分开构建；独立的桌面 TICI 查看器由 `backend/viewer_main.py` 提供，其本地数据库与中心服务分开。双端部署见 [客户端与管理后台](CLIENT_ADMIN_SPLIT.md)。

## 1. 初始化

在空 MySQL 8 数据库中执行 `database/schema.sql`；已有 LungTic 数据库先备份，然后依次执行尚未执行的 `database/migrations/phase3.sql` 和 `database/migrations/phase4_record_encryption.sql`（每个迁移只执行一次）。如果已执行阶段 3，只执行阶段 4。旧患者迁移后没有诊疗分配，普通医师默认看不到，须由管理员核实后分配。不要把病例、备份或密钥提交到 GitHub。

PowerShell 示例（将占位值换成私有配置，不写进仓库）：

```powershell
$env:LUNGTIC_DB_URL = "mysql+pymysql://USER:PASSWORD@127.0.0.1:3306/lungtic"
$env:LUNGTIC_JWT_SECRET = "<独立生成的至少32字符随机密钥>"
$env:LUNGTIC_CAPTCHA_SECRET = "<另一条至少32字符随机密钥>"
$env:LUNGTIC_CORS_ORIGINS = "app://lungtic,https://admin.example.org"
$env:LUNGTIC_DATA_DIR = "D:\LungTic-private-data"
$env:LUNGTIC_RECORD_ACTIVE_KEY_ID = "v1"
$env:LUNGTIC_RECORD_KEYS_JSON = '{"v1":"<32字节随机密钥的Base64编码>"}'
$env:LUNGTIC_BOOTSTRAP_USERNAME = "admin"
$env:LUNGTIC_BOOTSTRAP_PASSWORD = "<至少12字符的初始密码>"
cd backend
python bootstrap_admin.py
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

`bootstrap_admin.py` 可重复运行，会更新指定管理员密码。示例 URL 中的 `USER` 和 `PASSWORD` 必须替换为真实的 MySQL 账号与密码；错误 `1045 Access denied for user 'USER'` 表示仍在使用占位值。服务入口 `main.py` 缺少数据库 URL、私有数据目录、JWT/验证码密钥、附件加密密钥或明确 CORS 来源时会拒绝启动。附件加密密钥须由安全的密钥管理系统保存并注入进程；丢失密钥后附件无法恢复。默认监听本机；跨机器访问需由部署方配置内网 HTTPS 反向代理、访问控制与文件权限。服务默认将 `OPENBLAS_NUM_THREADS` 设为 1，避免空闲数值库预留大量线程内存；如机构经压测需要更多 BLAS 并行度，可在启动前显式设置该环境变量。PyTorch 模型在首次推理时加载，首次运行会增加内存和启动时延。开发时在 `frontend` 下运行 `npm run dev` 启动临床客户端，运行 `npm run dev:admin` 启动管理后台；两个开发代理均指向本机 8000 端口。生产环境须将管理后台实际 HTTPS 域名加入 CORS 来源；开发调试另加 `http://127.0.0.1:5173` 和 `http://127.0.0.1:5174`。接口文档位于 `/docs`。

## 2. 设置科室与诊疗关系

1. 管理员通过独立浏览器管理后台登录；医生和患者通过桌面客户端登录。中心服务登录必须提交图形验证码。
2. 管理员通过 `POST /api/auth/users` 创建医师账号，密码至少 12 字符；通过 `POST /api/organization/departments` 创建科室。
3. 用 `PUT /api/organization/departments/{department_id}/members/{user_id}` 设置医师所属科室；科主任设置 `is_head=true`。只有有效成员关系生效。
4. 医师在“患者列表”输入编码创建病例，或上传 DICOM、NIfTI、TICI。只有该科诊疗医师能写入自己获分配的患者。
5. 对迁移的旧患者，管理员用 `GET /api/organization/patients` 找到 ID，再用 `PUT /api/organization/patients/{patient_id}/care-team/{user_id}` 分配医师；首次设置主责科室时传 `set_primary=true`。停用分配会立即撤销该医师基于诊疗团队的访问权。
6. 科主任可用 `POST /api/organization/patients/{patient_id}/grants` 给指定医师发出带用途、到期时间和读写范围的会诊授权；`DELETE /api/organization/grants/{grant_id}` 立即撤销。管理员也能管理授权，但管理员身份本身不赋予病例正文读取权。

已有患者编码可以由管理员创建患者账号时绑定到尚未绑定账号的病例。医师可单独设置附件是否向该患者账号可见，默认不可见。

## 3. 病例接口与边界

| 操作 | 接口 | 条件 |
| --- | --- | --- |
| 授权患者列表 | `GET /api/dicom/patients` | 医师诊疗分配、科主任主责科室、有效会诊或患者本人 |
| 创建病例 | `POST /api/patients` | 有效科室成员的医师 |
| 病例读写能力 | `GET /api/patients/{id}/access` | 有该患者读取权 |
| 附件列表/上传 | `GET/POST /api/patients/{id}/records` | 读取/写入权 |
| 附件详情/下载 | `GET /api/records/{id}`、`GET /api/records/{id}/download` | 每次按患者重新鉴权 |
| 患者可见范围 | `PUT /api/records/{id}/visibility` | 有该患者写入权 |
| DICOM/NIfTI、TICI | `POST /api/dicom/upload`、`POST /api/tici/import` | 有效科室成员的医师；已有患者须有写入权 |
| 审计查询 | `GET /api/organization/audit-events` | 管理员，仅元数据 |

PDF、PNG、JPEG、DICOM、TICI **附件**采用私有文件夹和服务端随机存储键；上传校验扩展名、内容签名和 512 MB 上限，记录明文与密文 SHA-256，同一患者重复文件返回已有索引。附件使用随机单文件 AES-256-GCM 密钥加密，主密钥只用于包裹单文件密钥；下载前校验 GCM 认证标签、明文哈希、密文哈希和文件长度，失败时拒绝返回明文。可用 `GET /api/records/{id}/integrity` 主动校验。影像 DICOM 单文件上限 64 MB，单次请求总量上限 512 MB。服务端下载前校验实时权限，文件路径不出现在 API 响应中。科主任读本科室当前主责患者；会诊只在未过期、未撤销的授权范围内生效。

## 4. 明文迁移与密钥轮换

阶段 4 迁移后，旧附件标记为 `encryption_version=0`，接口会拒绝下载，直到离线加密完成。停止中心服务并备份数据库和私有数据目录后，在同一组密钥环境变量下执行：

```powershell
cd backend
python encrypt_legacy_records.py
python encrypt_legacy_records.py --apply
```

脚本在每个附件的原有 SHA-256 和大小匹配、密文 GCM 校验通过后，才更新数据库索引并删除旧文件。操作系统快照、备份及磁盘空闲块里可能仍残留历史明文，必须由部署方按存储介质和保留策略处理。

轮换主密钥时，先把新旧密钥都放进 `LUNGTIC_RECORD_KEYS_JSON`，把 `LUNGTIC_RECORD_ACTIVE_KEY_ID` 指向新密钥；停服务、备份数据库，再执行：

```powershell
python rewrap_record_keys.py
python rewrap_record_keys.py --apply
```

脚本仅重新包裹单文件密钥，不重写附件密文。确认所有记录都指向新密钥且抽样下载通过后，再从服务配置中移除旧密钥。密钥和数据库/文件备份应分别保护。

**覆盖范围：** 这一阶段的应用层加密针对 `clinical_records` 附件。原有 DICOM/NIfTI/TICI 影像库、AI 中间产物、数据库中的患者编码与元数据仍需由加密卷或等效存储加密保护。FastAPI 的 multipart 上传可能先把明文暂存到磁盘；中心服务把临时目录设在 `LUNGTIC_DATA_DIR/tmp`，因此整个数据目录及备份必须位于受控的加密存储上。临时目录和数据目录均应限制为服务账号访问。下载会将解密内容暂存于同一受控数据目录中的自动删除临时文件，完整验证 GCM 标签与哈希后才按 1 MB 分块发送；单附件上限 512 MB。临时明文及存储介质的快照仍须依赖加密卷和访问控制保护。正式部署前还需做并发容量与限流测试。

## 5. 验证与下一阶段

```powershell
cd backend
python -m pip install -r requirements-dev.txt
python -m pytest -q tests/test_clinical_access.py
cd ..\frontend
npm run build
npm run build:admin
```

本分支已做患者/检查/切片/TICI/AI 结果的对象级权限检查、附件认证加密与哈希校验、受控上传下载、科室与会诊授权、基础审计及前端入口。下一阶段仍需：异步与可续传的大文件处理、文件版本和更正流程、请求关联 ID、备份恢复演练、登录与上传限流、恶意文件扫描、前端令牌存储改造、机构身份集成及生产环境安全审查。当前实现不应直接用于真实患者数据的公开互联网部署。

加密设计依据：[cryptography 的 GCM 接口文档](https://cryptography.io/en/stable/hazmat/primitives/symmetric-encryption/)说明认证标签须在完整解密后验证；[NIST SP 800-38D](https://csrc.nist.gov/pubs/sp/800/38/d/final)规定 GCM 的认证加密用途。SHA-256 用于校验和去重，保密性与防篡改由 AES-GCM 和受保护的密钥提供。

## 6. Windows 独立服务包（目标机器无需安装 Python）

在已装好构建依赖的开发机运行 `powershell -ExecutionPolicy Bypass -File backend/scripts/package-server.ps1 -BuildPython "D:\envs\lungtic-training\python.exe"`，得到忽略于 Git 的 `backend-dist/LungTic-Server` 目录。复制整个目录到服务机器；里面有 `LungTic-Server.exe`、Python 运行时、依赖、数据库 SQL 和中文说明。使用目录模式可以避免每次启动都解压数 GB 文件。构建时需要 Python 与 PyInstaller，运行时不需要。AI 模型权重、病例、数据库、TLS 私钥和服务密钥均不在包内。

在服务机器将 `server.env.example.ps1` 复制为仅服务账号可读的 `server.env.ps1`，填写真实数据库、数据目录和独立密钥，然后运行 `powershell -ExecutionPolicy Bypass -File start-server.ps1`。启动脚本默认监听 `127.0.0.1:8000`，只允许本机 HTTPS 反向代理接入；客户端安装版仍须配置有效证书和服务器公钥指纹。修改端口可传 `-Port 18080`。演示数据可以使用 SQLite，但需先创建表和管理员；生产应按本文件第 1 节准备数据库。服务目录可以更换，私有数据目录和配置文件应与可执行程序分开备份与保护。

本机已建立一个与 MySQL 隔离的合成数据演示配置 `backend/.env.demo.ps1`（被 Git 忽略）。可在项目根目录先执行 `. .\backend\.env.demo.ps1`，再运行 `& .\backend-dist\LungTic-Server\LungTic-Server.exe --host 127.0.0.1 --port 8000`。这一运行路径无需再安装 Python，也不会使用之前报错的 MySQL `USER` 占位账号。该 HTTP 演示服务仅供本机开发代理访问；安装版桌面客户端需要机构 HTTPS 服务和可信证书。
