# 中心病例服务：运行与权限

本分支提供 FastAPI + MySQL 的病例服务 MVP。使用合成数据验证；上线处理真实病例前，仍需完成医院内网部署、安全评估、备份恢复和数据治理流程。独立的桌面 TICI 查看器由 `backend/viewer_main.py` 提供，其本地数据库与中心服务分开。

## 1. 初始化

在空 MySQL 8 数据库中执行 `database/schema.sql`；已有 LungTic 数据库先备份，然后只执行一次 `database/migrations/phase3.sql`。旧患者迁移后没有诊疗分配，普通医师默认看不到，须由管理员核实后分配。不要把病例、备份或密钥提交到 GitHub。

PowerShell 示例（将占位值换成私有配置，不写进仓库）：

```powershell
$env:LUNGTIC_DB_URL = "mysql+pymysql://USER:PASSWORD@127.0.0.1:3306/lungtic"
$env:LUNGTIC_JWT_SECRET = "<独立生成的至少32字符随机密钥>"
$env:LUNGTIC_CAPTCHA_SECRET = "<另一条至少32字符随机密钥>"
$env:LUNGTIC_CORS_ORIGINS = "http://127.0.0.1:5173"
$env:LUNGTIC_DATA_DIR = "D:\LungTic-private-data"
$env:LUNGTIC_BOOTSTRAP_USERNAME = "admin"
$env:LUNGTIC_BOOTSTRAP_PASSWORD = "<至少12字符的初始密码>"
cd backend
python bootstrap_admin.py
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

`bootstrap_admin.py` 可重复运行，会更新指定管理员密码。服务入口 `main.py` 缺少数据库 URL、随机密钥或明确 CORS 来源时会拒绝启动。默认监听本机；跨机器访问需由部署方配置内网 HTTPS 反向代理、访问控制与文件权限。前端通过 `frontend` 下的 `npm run dev` 启动，开发代理指向本机 8000 端口。接口文档位于 `/docs`。

## 2. 设置科室与诊疗关系

1. 管理员通过前端登录。中心服务登录必须提交图形验证码。
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

PDF、PNG、JPEG、DICOM、TICI 附件采用私有文件夹和服务端随机存储键；上传校验扩展名、内容签名和 512 MB 上限，记录 SHA-256，同一患者重复文件返回已有索引。影像 DICOM 单文件上限 64 MB，单次请求总量上限 512 MB。服务端下载前校验实时权限，文件路径不出现在 API 响应中。科主任读本科室当前主责患者；会诊只在未过期、未撤销的授权范围内生效。

## 4. 验证与下一阶段

```powershell
cd backend
python -m pip install -r requirements-dev.txt
python -m pytest -q tests/test_clinical_access.py
cd ..\frontend
npm run build
```

本分支已做患者/检查/切片/TICI/AI 结果的对象级权限检查、受控附件上传下载、科室与会诊授权、基础审计及前端入口。下一阶段仍需：异步与可续传的大文件处理、文件版本和更正流程、请求关联 ID、备份恢复演练、登录与上传限流、恶意文件扫描、前端令牌存储改造、机构身份集成及生产环境安全审查。当前实现不应直接用于真实患者数据的公开互联网部署。
