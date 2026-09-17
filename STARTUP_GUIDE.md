# LungTic 启动指南

## 环境要求

- Python 3.10+
- Node.js 18+
- MySQL 8.0+
- npm 9+

---

## 第一步：数据库

```powershell
# 启动 MySQL 服务，然后执行建表脚本
mysql -u root -p < database/schema.sql
```

这会创建 `lungtic` 数据库，包含 10 张表，并插入默认 admin 账号。

---

## 第二步：后端

```powershell
cd backend

# 创建虚拟环境 (推荐)
python -m venv venv
.\venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 启动 (运行在 http://127.0.0.1:8000)
python main.py
```

验证：浏览器打开 http://127.0.0.1:8000/api/health
应返回 `{"status":"ok","app":"LungTic"}`

---

## 第三步：前端

```powershell
cd frontend
npm install
npm run dev           # 浏览器模式 (http://localhost:5173)
# 或
npm run electron:dev  # Electron 桌面模式
```

---

## 第四步：登录

打开 http://localhost:5173

- 用户名: `admin`
- 密码: `admin123`

---

## 环境变量 (可选)

| 变量 | 默认值 |
|------|--------|
| `LUNGTIC_DB_URL` | `mysql+pymysql://root:root@localhost:3306/lungtic` |
| `LUNGTIC_JWT_SECRET` | `lungtic-dev-secret-change-in-prod` |

---

## 目录结构说明

| 目录 | 用途 |
|------|------|
| `backend/data/models/` | 用户上传的 .pth / .onnx 模型 |
| `backend/data/dicom/` | 上传的 DICOM 文件 + 分割结果 |
| `frontend/dist/` | 前端构建产物 |

---

## 常见问题

**Q: 数据库连接失败**
检查 MySQL 是否运行，`config.py` 中的 `DATABASE_URL` 是否正确。

**Q: npm install 失败**
确保 Node.js >= 18，可尝试 `npm install --legacy-peer-deps`。

**Q: PyTorch 安装慢**
使用清华镜像: `pip install torch -i https://pypi.tuna.tsinghua.edu.cn/simple`

**Q: 端口占用**
后端默认 8000，前端默认 5173。修改 `backend/main.py` 和 `frontend/vite.config.ts`。
