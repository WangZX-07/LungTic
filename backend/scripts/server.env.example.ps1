# 复制为 server.env.ps1 后填写真实值；不要提交到 GitHub。
# 仅限合成数据演示时可使用 SQLite；真实病例按医院要求使用受控数据库。
$env:LUNGTIC_DB_URL = 'sqlite:///D:/LungTic-private-data/lungtic.sqlite'
$env:LUNGTIC_DATA_DIR = 'D:\LungTic-private-data'
$env:LUNGTIC_JWT_SECRET = '<至少 32 字符的独立随机密钥>'
$env:LUNGTIC_CAPTCHA_SECRET = '<另一条至少 32 字符的随机密钥>'
$env:LUNGTIC_CORS_ORIGINS = 'app://lungtic,https://admin.example.org'
$env:LUNGTIC_RECORD_ACTIVE_KEY_ID = 'v1'
$env:LUNGTIC_RECORD_KEYS_JSON = '{"v1":"<32 字节随机密钥的 Base64>"}'
