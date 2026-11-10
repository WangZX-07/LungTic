# 项目材料清单

## 活跃源码

- `backend/`：中心 API、权限、加密、通知、SMTP、影像与 AI 服务
- `frontend/`：临床客户端、管理后台、Electron 主进程和打包脚本
- `database/`：全量 schema 和 phase2–phase6 迁移
- `tici/`：TICI 格式读写、转换与测试

## 核心文档

- `README.md`：开发、构建和部署入口
- `HANDOFF.md`：架构、安全、运维和接手清单
- `ARCHITECTURE.md`：系统架构
- `PROJECT_SUMMARY.md`：项目概况
- `UI_COMPONENT_TREE.md`：前端组件树
- `STARTUP_GUIDE.md`：Windows 快速启动
- `docs/CLINICAL_SERVER.md`：中心服务部署
- `docs/CLIENT_ADMIN_SPLIT.md`：客户端/管理后台拆分和安全说明
- `docs/TICI_VIEWER.md`：单机查看器说明

## 设计与知识产权材料

- `LungTic-V1.0.0源代码.docx`
- `docs/程序设计说明书.docx`
- `docs/patent/`：专利请求书、说明书、摘要、附图和生成脚本
- `docs/superpowers/`、`docs/plans/`：历史设计规格和实施计划

## 历史材料

- `docs/archive/README_LEGACY.md`
- `docs/archive/PROJECT_FEATURES_LEGACY.md`
- `tools/legacy/`：一次性修复脚本，仅用于追溯，不应执行

## 本地生成但不提交的内容

- `frontend/node_modules/`、`frontend/dist/`、`frontend/dist-admin/`
- `frontend/release*/`
- `backend-dist/`、`build/`
- `backend/data/`、本地数据库、病例、模型权重
- `.env*`、证书私钥和服务环境文件

这些目录可能保留在当前工作副本中以便继续开发，但由根目录 `.gitignore` 排除。对外移交源码时应从干净克隆重新构建，不依赖现有生成物。
