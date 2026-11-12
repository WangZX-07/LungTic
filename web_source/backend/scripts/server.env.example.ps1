# 复制为 server.env.ps1 后填写真实值；不要提交到 GitHub。
# 仅限合成数据演示时可使用 SQLite；真实病例按医院要求使用受控数据库。
$env:LUNGTIC_DB_URL = 'sqlite:///D:/LungTic-private-data/lungtic.sqlite'
$env:LUNGTIC_DATA_DIR = 'D:\LungTic-private-data'
$env:LUNGTIC_JWT_SECRET = '<至少 32 字符的独立随机密钥>'
$env:LUNGTIC_CAPTCHA_SECRET = '<另一条至少 32 字符的随机密钥>'
$env:LUNGTIC_CORS_ORIGINS = 'app://lungtic,https://admin.example.org,https://project.example.org'
$env:LUNGTIC_RECORD_ACTIVE_KEY_ID = 'v1'
$env:LUNGTIC_RECORD_KEYS_JSON = '{"v1":"<32 字节随机密钥的 Base64>"}'

# 可选：LungTic 单项目进度门户。飞书和 GitHub 密钥只保存在服务端。
$env:LUNGTIC_PROJECT_ORIGIN = 'https://project.example.org'
$env:LUNGTIC_PROJECT_COOKIE_SECURE = '1'
$env:LUNGTIC_FEISHU_APP_ID = '<cli_开头的 App ID>'
$env:LUNGTIC_FEISHU_APP_SECRET = '<飞书 App Secret>'
$env:LUNGTIC_FEISHU_REDIRECT_URI = 'https://project.example.org/api/project/auth/callback'
$env:LUNGTIC_PROJECT_BOOTSTRAP_OPEN_IDS = '<首位项目管理员的 ou_ Open ID>'
$env:LUNGTIC_GITHUB_REPOSITORY = 'owner/repository'
$env:LUNGTIC_GITHUB_WEBHOOK_SECRET = '<独立随机 Webhook Secret>'
$env:LUNGTIC_GITHUB_API_TOKEN = '<可选；私有仓库历史同步必须配置的只读 Fine-grained Token>'
