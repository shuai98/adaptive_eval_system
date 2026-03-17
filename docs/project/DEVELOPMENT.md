# 开发环境配置指南

## 📦 虚拟环境信息

### 使用的虚拟环境
- **环境名称**：`FastAPI_env`
- **环境管理器**：Conda
- **Python 版本**：3.9+

### 激活虚拟环境

```bash
# Windows
conda activate FastAPI_env

# Linux/Mac
conda activate FastAPI_env
```

### 创建新的虚拟环境（如果需要）

```bash
# 创建环境
conda create -n FastAPI_env python=3.9

# 激活环境
conda activate FastAPI_env

# 安装依赖
pip install -r requirements.txt
```

---

## 🗄️ 数据库配置

### MySQL 配置

**数据库名称**：`adaptive_eval`（注意不是 adaptive_exam）

**连接信息**：
- Host: `localhost` (127.0.0.1)
- Port: `3306`
- User: `root`
- Password: `123456`（请修改为你的密码）
- Database: `adaptive_eval`

### 创建数据库

```sql
CREATE DATABASE adaptive_eval CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 初始化数据库表

```bash
conda activate FastAPI_env
python backend/scripts/init_db.py
```

### 数据库迁移（添加 question_id 字段）

```bash
conda activate FastAPI_env
python migrate_simple.py
```

或者双击运行：`run_migrate.bat`

---

## 🚀 启动项目

### 1. 启动 Redis（如果使用缓存）

```bash
redis-server
```

### 2. 启动后端服务

```bash
conda activate FastAPI_env
cd d:\BiShe_code\adaptive_eval_system
python backend/main.py
```

或者使用 uvicorn：

```bash
conda activate FastAPI_env
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8088
```

### 3. 访问系统

- **登录页面**：http://127.0.0.1:8088/static/login.html
- **API 文档**：http://127.0.0.1:8088/docs

---

## 🔑 环境变量配置

在项目根目录创建 `.env` 文件：

```env
# DeepSeek API Key
DEEPSEEK_API_KEY=sk-your-api-key-here

# MySQL 配置
MYSQL_USER=root
MYSQL_PASSWORD=123456
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DB=adaptive_eval

# Redis 配置
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0

# HuggingFace 镜像源（国内加速）
HF_ENDPOINT=https://hf-mirror.com
```

---

## 📝 常用命令

### 创建管理员账号

```bash
conda activate FastAPI_env
python backend/scripts/create_admin.py
```

### 初始化 RAG 向量库

```bash
conda activate FastAPI_env
python backend/scripts/init_rag.py
```

### 运行测试

```bash
conda activate FastAPI_env

# 测试 LLM 连接
python tests/test_llm.py

# 测试 RAG 检索
python tests/test_rag.py

# 测试 Redis 连接
python tests/test_redis_connection.py

# 测试自适应统计
python tests/test_adaptive_stats.py
```

---

## 🛠️ 开发工具

### 推荐的 IDE
- **VS Code** / **Cursor**
- **PyCharm Professional**

### 推荐的插件（VS Code）
- Python
- Pylance
- SQLTools
- REST Client
- GitLens

### 代码格式化

```bash
# 安装 black
pip install black

# 格式化代码
black backend/
```

---

## 📂 项目目录说明

```
adaptive_eval_system/
├── backend/                    # 后端代码
│   ├── api/                   # API 路由层
│   ├── core/                  # 核心配置
│   ├── db/                    # 数据库连接
│   ├── models/                # 数据模型
│   ├── services/              # 业务逻辑层
│   ├── scripts/               # 工具脚本
│   └── main.py               # 启动入口
├── frontend/                   # 前端代码
│   ├── student/              # 学生端
│   ├── teacher/              # 教师端
│   ├── admin/                # 管理端
│   └── login.html            # 登录页
├── data/                       # 数据目录
│   ├── docs/                 # 知识库文档
│   ├── faiss_index/          # 向量索引
│   └── app.db                # SQLite（已废弃）
├── tests/                      # 测试文件
├── notes/                      # 开发笔记
├── .env                        # 环境变量（需创建）
├── requirements.txt            # Python 依赖
├── migrate_simple.py           # 数据库迁移脚本
├── run_migrate.bat            # 迁移脚本快捷方式
└── README.md                  # 项目说明
```

---

## 🗑️ 可以删除的文件

### 临时文件
- `__pycache__/` 目录（所有）
- `*.pyc` 文件
- `.DS_Store`（Mac）

### 废弃文件
- `data/app.db`（已改用 MySQL）
- `update_db.py`（功能已整合到 migrate_simple.py）
- `pack_code.py`（打包工具，非必需）
- `project_context.txt`（临时文件）
- `My_note.md`（个人笔记，可移到 notes/）
- `README.pdf`（可以从 README.md 重新生成）

### 测试日志
- `backend/services/metrics/locust_debug.log`

---

## 🐛 常见问题

### 1. 数据库连接失败

**错误**：`Unknown database 'adaptive_exam'`

**解决**：数据库名称应该是 `adaptive_eval`，检查 `.env` 文件配置。

### 2. 模块导入失败

**错误**：`ModuleNotFoundError: No module named 'backend'`

**解决**：确保在项目根目录运行命令，并激活了虚拟环境。

### 3. Redis 连接失败

**错误**：`Redis connection failed`

**解决**：
1. 检查 Redis 是否启动：`redis-cli ping`
2. 如果不需要缓存，系统会自动降级（不影响使用）

### 4. FAISS 索引加载失败

**错误**：`FAISS load failed`

**解决**：运行 `python backend/scripts/init_rag.py` 重新生成索引。

---

## 📞 技术支持

如有问题，请查看：
1. `notes/04_问题与Bug.md` - 已知问题列表
2. `notes/06_答辩准备.md` - 常见问题解答
3. GitHub Issues

---

**最后更新**：2026-02-10

