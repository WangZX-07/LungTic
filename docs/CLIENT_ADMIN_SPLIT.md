# LungTic 双端与中心服务

## 已实现的边界

| 部分 | 入口与构建 | 使用者 | 作用 |
| --- | --- | --- | --- |
| 临床桌面端 | `frontend/index.html` / `npm run package:client` | 医生、患者 | 连接中心 API，按服务端授权查看和上传病例 |
| 浏览器管理后台 | `frontend/admin.html` / `npm run build:admin` | 管理员 | 管理账号、科室、诊疗团队、限时授权、访问审计 |
| 中心服务 | `backend/main.py` | 两端 | 认证、对象级权限、病历附件加密和哈希校验 |
| 旧版离线阅片器 | `npm run package:viewer` | 本地阅片器管理员 | 本机 SQLite；不连接中心病例库 |

桌面构建不含管理后台路由和用户管理页面；管理后台使用独立的管理员会话。界面分离只是产品边界，真正权限仍在中心服务按角色、科室、诊疗分配和限时授权逐项校验。管理员身份不能直接读取病例正文。

## 本地开发

先按 [中心服务运行说明](CLINICAL_SERVER.md) 启动 FastAPI 和数据库。两个 Vite 开发代理均转发 `/api` 至本机 8000 端口。

```powershell
cd frontend
npm install
npm run dev                  # 医生/患者客户端：http://localhost:5173
npm run dev:admin            # 管理后台：http://localhost:5174/admin.html
npm run electron:client:dev  # Electron 开发窗口
```

安装后的桌面端首次登录前，在登录页设置医院服务端 HTTPS 根地址，例如 `https://clinical.example.org`，不带 `/api`。只有本机调试可使用 `http://localhost` 或 `http://127.0.0.1`。桌面端目前将服务地址和登录令牌保存在本机 Web 存储；接入真实患者数据前须评估终端加密、会话锁定和令牌保护。

## 构建与部署

```powershell
cd frontend
npm run build:admin     # 输出 frontend/dist-admin；作为独立静态站点部署
npm run package:client  # 输出 frontend/release-client；不捆绑后端或本地数据库
```

管理后台建议部署在独立 HTTPS 域名，如 `https://admin.example.org`，由反向代理将 `/api` 转发至中心服务。若 API 使用另一个域名，构建时设置 `VITE_ADMIN_API_BASE_URL=https://clinical.example.org/api`。中心服务的 `LUNGTIC_CORS_ORIGINS` 要明确列出 `app://lungtic` 与管理后台实际 HTTPS 来源，不使用通配符。浏览器后台应由 HTTPS 代理提供 CSP、HSTS 等响应头。不要将后端数据目录、密钥或令牌打包进前端。

当前生成的 Windows 安装包尚未进行可信代码签名；正式分发前须配置机构代码签名证书，并在干净终端验证安装、更新和卸载。

离线阅片器的 `package:viewer` 构建继续存在，输出在 `frontend/release`。它使用本地演示账户与 SQLite，不能代替中心临床客户端处理真实病例。

## 接下来的实施计划

1. **机构身份与终端安全**：接入医院统一身份、短会话与刷新机制，给桌面令牌使用系统凭据库或等效保护；增加闲置锁定和终端注销。
2. **授权审批**：在当前管理员/科主任可直接发放限时授权的基础上，加入医师申请、审批、拒绝和到期通知，保留理由与审计链。
3. **完整数据加密**：当前 AES-256-GCM 与 SHA-256 覆盖病历附件。把原始 DICOM/NIfTI/TICI、AI 派生文件和备份也纳入受控加密存储，演练密钥轮换与恢复。
4. **生产验证**：大文件上传与限流、恶意文件扫描、并发和故障恢复、审计防篡改、独立安全测试与合作医院的数据治理确认。首批部署只使用合成或充分去标识化数据。
