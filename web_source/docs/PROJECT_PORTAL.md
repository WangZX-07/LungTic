# LungTic 项目进度门户部署与交接

项目门户是独立站点，建议域名为 `https://project.respulse.top`。它只管理 LungTic 项目的里程碑、任务、人工进度、风险和 GitHub 动态，不复用临床账号，也不能读取病例数据。

部署完成后的部门 ID、职位同步、角色映射和日常操作见 [PROJECT_PORTAL_USER_GUIDE.md](PROJECT_PORTAL_USER_GUIDE.md)。

## 1. 访问与权限模型

| 项目角色 | 能力 |
|---|---|
| `project_admin` | 集成状态、飞书映射规则、成员手动角色、GitHub 账号绑定及全部项目管理能力 |
| `project_lead` | 里程碑、任务、风险和全部进度管理 |
| `team_lead` | 创建/分配任务、更新全部任务和风险、提交进度 |
| `contributor` | 查看项目、更新本人任务、提交本人进度、登记风险 |
| `observer` | 只读查看 |
| `unassigned` | 拒绝进入；等待管理员配置映射 |

项目角色仅存在于 `project_*` 数据表。它与 `users` 表中的医生、患者和管理员角色没有继承或转换关系。

登录时服务端读取飞书 Open ID、部门和职位，按启用规则的优先级从高到低匹配。同一条规则同时填写部门和职位时，两个条件必须同时满足。`manual_role` 是管理员显式覆写，优先于自动映射。

## 2. 飞书自建应用

1. 在飞书开放平台创建企业自建应用，保存 App ID 和 App Secret；App Secret 只放服务器环境文件。
2. 启用“网页应用”，将桌面端主页和移动端主页都设置为：

   ```text
   https://project.respulse.top
   ```

3. 在安全设置中添加重定向 URL，必须逐字一致：

   ```text
   https://project.respulse.top/api/project/auth/callback
   ```

4. 为应用申请读取当前用户基础资料、部门与职位所需的最小通讯录权限，并把需要使用门户的部门加入应用可用范围。权限名称随开放平台版本可能调整，应以“获取单个用户” Contact v3 API 调试台显示的必需权限为准。
5. 发布应用并由企业管理员审核。在飞书工作台打开时前端优先调用 `tt.requestAccess`；旧客户端回退到 `requestAuthCode`；普通浏览器重定向到飞书官方扫码/密码登录页。
6. 使用 API 调试台取得首位项目管理员的应用内 Open ID（`ou_...`），写入后述 `LUNGTIC_PROJECT_BOOTSTRAP_OPEN_IDS`。首位管理员成功登录后，应在项目设置中创建正式部门/职位规则；确认其他管理员可用后，可从环境变量移除引导 Open ID。

飞书登录 code 为一次性且短时有效，不能重放。服务端换取用户身份后建立自己的 7 天会话，只在数据库保存会话令牌和 CSRF 令牌的 SHA-256 摘要。

## 3. GitHub 自动同步

在 GitHub 仓库 Settings → Webhooks 新建 Webhook：

- Payload URL：`https://project.respulse.top/api/project/integrations/github/webhook`
- Content type：`application/json`
- Secret：使用独立随机值，和服务器 `LUNGTIC_GITHUB_WEBHOOK_SECRET` 完全一致
- Events：Push、Pull requests、Issues、Workflow runs、Releases
- SSL verification：启用

服务端先按原始请求体校验 `X-Hub-Signature-256`，再检查仓库全名和 `X-GitHub-Delivery` 去重。已关联任务的 PR 合并或 Issue 关闭时，任务自动变为 100%；其他 GitHub 动态只作为证据，不自动修改项目完成度。

生成 Webhook Secret：

```bash
openssl rand -hex 32
```

不要把 Secret 写入仓库、截图或 GitHub Webhook URL。

## 4. 服务器环境变量

在 `/etc/lungtic/server.env` 追加以下内容，文件权限保持 `0600`：

```ini
LUNGTIC_PROJECT_ORIGIN=https://project.respulse.top
LUNGTIC_PROJECT_COOKIE_SECURE=1
LUNGTIC_FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
LUNGTIC_FEISHU_APP_SECRET=从飞书后台复制的密钥
LUNGTIC_FEISHU_REDIRECT_URI=https://project.respulse.top/api/project/auth/callback
LUNGTIC_PROJECT_BOOTSTRAP_OPEN_IDS=ou_xxxxxxxxxxxxxxxx
LUNGTIC_GITHUB_REPOSITORY=WangZX-07/LungTic
LUNGTIC_GITHUB_WEBHOOK_SECRET=openssl生成的独立随机值
LUNGTIC_GITHUB_API_TOKEN=可选的只读Fine-grainedToken；私有仓库历史同步必填
```

公开仓库同步历史时可以暂不填写 `LUNGTIC_GITHUB_API_TOKEN`，但会受到较低的匿名 API 请求额度限制。私有仓库必须配置只读 Token，至少开放目标仓库 Metadata、Contents、Issues、Pull requests 和 Actions 的读取权限。Token 只放在服务器环境文件，不发送给前端。

同时在原有 `LUNGTIC_CORS_ORIGINS` 中加入 `https://project.respulse.top`。生产环境不得使用 `*`。

编辑并保护文件：

```bash
sudo nano /etc/lungtic/server.env
sudo chown root:root /etc/lungtic/server.env
sudo chmod 600 /etc/lungtic/server.env
```

## 5. 数据库迁移与构建

执行前先做 MySQL 备份，然后在仓库根目录运行：

```bash
cd /opt/lungtic/app/web_source
mysql -u root -p < database/migrations/phase7_project_portal.sql

cd frontend
npm ci
npm run build:project
sudo mkdir -p /var/www/lungtic-project
sudo rsync -a --delete dist-project/ /var/www/lungtic-project/

sudo systemctl restart lungtic
sudo systemctl status lungtic --no-pager -l
```

`rsync --delete` 的目标必须是上面明确创建的 `/var/www/lungtic-project/`，不要改成仓库根目录或其他宽泛路径。

## 6. Nginx 独立站点

先给 `project.respulse.top` 添加指向服务器公网 IP 的 A 记录。在证书申请前，确保安全组和防火墙允许 80/443。

HTTP 验证与跳转站点：

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name project.respulse.top;

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/certbot;
        default_type text/plain;
        try_files $uri =404;
    }

    location / { return 301 https://$host$request_uri; }
}
```

确认 `http://project.respulse.top/.well-known/acme-challenge/test` 可访问后申请证书，再加入 HTTPS 站点：

```nginx
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name project.respulse.top;

    ssl_certificate /etc/letsencrypt/live/project.respulse.top/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/project.respulse.top/privkey.pem;

    root /var/www/lungtic-project;
    index project.html;
    client_max_body_size 2m;

    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy strict-origin-when-cross-origin always;
    add_header X-Frame-Options SAMEORIGIN always;
    add_header Strict-Transport-Security "max-age=31536000" always;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }

    location / {
        try_files $uri $uri/ /project.html;
    }
}
```

启用并验证：

```bash
sudo nginx -t
sudo systemctl reload nginx
curl -I https://project.respulse.top
curl https://project.respulse.top/api/project/auth/config
```

## 7. 上线验收

1. 普通浏览器访问项目域名，确认进入飞书官方扫码登录。
2. 在飞书工作台打开，确认当前账号可免登或安全回退到官方授权页。
3. 未匹配规则的成员应收到“尚未映射项目权限”，不能进入项目数据。
4. 观察者的写请求应返回 403；成员只能更新自己的任务。
5. 管理员创建部门/职位规则，绑定成员 GitHub 登录名。
6. GitHub Webhook “Recent Deliveries” 返回 202；重复投递不会产生重复动态。
7. 关联测试 Issue/PR，关闭/合并后确认任务自动变为 100%。
8. 在 375px 宽手机和飞书移动端检查底部五项导航、表单、弹窗与安全区。

## 8. 本地开发

后端仍运行在 `127.0.0.1:8000`。另开终端启动项目门户：

```powershell
cd web_source\frontend
npm ci
npm run dev:project
```

访问 `http://127.0.0.1:5175`。本地没有可被飞书访问的 HTTPS 回调地址时，只能验证页面和使用自动化测试；完整飞书登录需使用已登记的 HTTPS 测试域名或受控隧道。
