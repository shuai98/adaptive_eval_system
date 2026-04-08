# 开发环境配置指南

## 基础环境

- Python：3.9+
- 推荐环境：`FastAPI_env`
- 环境管理器：Conda

```bash
conda activate FastAPI_env
```

如果需要新建环境：

```bash
conda create -n FastAPI_env python=3.9
conda activate FastAPI_env
pip install -r requirements.txt
```

## 数据库配置

项目当前使用 MySQL：

- Host：`127.0.0.1`
- Port：`3306`
- Database：`adaptive_eval`

创建数据库：

```sql
CREATE DATABASE adaptive_eval CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

初始化：

```bash
python backend/scripts/init_db.py
```

如果需要迁移脚本：

```bash
python migrate_simple.py
```

## 环境变量

在项目根目录创建 `.env`：

```env
APP_SECRET_KEY=replace-with-a-strong-secret
DEEPSEEK_API_KEY=sk-your-api-key-here

MYSQL_USER=root
MYSQL_PASSWORD=replace-with-your-password
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DB=adaptive_eval

REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0

ADMIN_BOOTSTRAP_USERNAME=root
ADMIN_BOOTSTRAP_PASSWORD=replace-with-a-strong-password
HF_ENDPOINT=https://hf-mirror.com
```

## 启动项目

### 1. 启动 Redis

```bash
redis-server
```

### 2. 启动后端

```bash
conda activate FastAPI_env
cd d:\BiShe_code\adaptive_eval_system
python backend/main.py
```

或使用 uvicorn：

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8088
```

### 3. 访问系统

- 主入口：`http://127.0.0.1:8088/static/app/index.html#/login`
- API 文档：`http://127.0.0.1:8088/docs`

兼容跳转入口仍保留：

- `http://127.0.0.1:8088/static/login.html`
- `http://127.0.0.1:8088/static/student/index.html`
- `http://127.0.0.1:8088/static/teacher/index.html`
- `http://127.0.0.1:8088/static/admin/index.html`

## 管理员初始化

```bash
python backend/scripts/create_admin.py
```

说明：

- 默认管理员用户名来自 `ADMIN_BOOTSTRAP_USERNAME`，默认值为 `root`
- `/lab` 研发管理中心仅允许 `root` 账号进入

## 前端说明

当前前端结构已经切换为：

- `frontend/app`：主 SPA
- `frontend/common`：共享 API / Session 工具
- `frontend/login.html`、`frontend/student/index.html`、`frontend/teacher/index.html`、`frontend/admin/index.html`：兼容跳转页

旧原生 JS/CSS 前端实现已不再作为主运行链路。

## 常用命令

```bash
python backend/scripts/init_rag.py
pytest tests/test_teacher_student_api.py
pytest tests/test_security_and_tasks.py
pytest tests/test_agent_api.py
```

## 推荐工具

- VS Code / Cursor
- PyCharm
- Python
- Pylance
- SQLTools
- GitLens

## 常见问题

### `Unknown database 'adaptive_exam'`

请检查 `.env`，数据库名应为 `adaptive_eval`。

### `ModuleNotFoundError: No module named 'backend'`

请确认在项目根目录执行命令，并已激活虚拟环境。

### Redis 连接失败

先检查 Redis 是否启动；如果当前场景不依赖缓存，部分能力会自动降级。

### FAISS 索引加载失败

重新执行：

```bash
python backend/scripts/init_rag.py
```
