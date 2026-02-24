# 项目文件清单

## 📋 文件分类说明

### ✅ 核心文件（必需）

#### 后端核心
- `backend/main.py` - 后端启动入口
- `backend/api/*.py` - API 路由层
- `backend/core/*.py` - 核心配置
- `backend/db/session.py` - 数据库连接
- `backend/models/tables.py` - 数据模型
- `backend/services/*.py` - 业务逻辑层

#### 前端核心
- `frontend/login.html` - 登录页面
- `frontend/student/*` - 学生端
- `frontend/teacher/*` - 教师端
- `frontend/admin/*` - 管理端

#### 配置文件
- `requirements.txt` - Python 依赖列表
- `.env` - 环境变量配置（需自己创建）
- `.gitignore` - Git 忽略规则
- `README.md` - 项目说明文档
- `DEVELOPMENT.md` - 开发环境配置文档

#### 数据文件
- `data/docs/*` - 知识库文档
- `data/faiss_index/*` - 向量索引

---

### 🛠️ 工具脚本（重要）

#### 初始化脚本
- `backend/scripts/init_db.py` - 初始化数据库表结构
- `backend/scripts/init_rag.py` - 初始化 RAG 向量库
- `backend/scripts/create_admin.py` - 创建管理员账号

#### 迁移脚本
- `migrate_simple.py` - 数据库迁移脚本（添加 question_id 字段）
- `run_migrate.bat` - 迁移脚本快捷方式（Windows）
- `backend/scripts/migrate_add_question_id.py` - 完整版迁移脚本

#### 清理脚本
- `clean_project.py` - 项目清理工具（删除临时文件）

---

### 🧪 测试文件（可选）

- `tests/test_llm.py` - 测试 LLM 连接
- `tests/test_rag.py` - 测试 RAG 检索
- `tests/test_redis_connection.py` - 测试 Redis 连接
- `tests/test_adaptive_stats.py` - 测试自适应统计接口
- `tests/test_grade.py` - 测试评分功能
- `tests/test_rerank.py` - 测试重排序功能

---

### 📝 文档文件（推荐保留）

- `notes/00_项目概述.md` - 项目概述
- `notes/01_技术选型.md` - 技术选型说明
- `notes/02_系统设计.md` - 系统设计文档
- `notes/03_实现过程.md` - 实现过程记录
- `notes/04_问题与Bug.md` - 问题与解决方案
- `notes/05_实验与结果.md` - 实验结果分析
- `notes/06_答辩准备.md` - 答辩准备材料
- `notes/07_自适应可视化功能.md` - 自适应可视化功能说明
- `notes/MyNote/*` - 个人笔记和截图

---

### 🗑️ 可以删除的文件

#### 临时文件
- `__pycache__/` - Python 缓存目录（所有位置）
- `*.pyc` - Python 字节码文件
- `*.log` - 日志文件
- `backend/services/metrics/locust_debug.log` - 测试日志

#### 废弃文件
- `data/app.db` - 已废弃的 SQLite 数据库（已改用 MySQL）
- `update_db.py` - 功能已整合到 migrate_simple.py
- `pack_code.py` - 打包工具（非必需）
- `project_context.txt` - 临时上下文文件
- `My_note.md` - 个人笔记（建议移到 notes/ 目录）
- `README.pdf` - 可从 README.md 重新生成

---

## 🔍 文件用途说明

### 虚拟环境相关

**虚拟环境名称**：`FastAPI_env`（Conda 环境）

**位置**：不在项目目录中，由 Conda 管理

**激活命令**：
```bash
conda activate FastAPI_env
```

### 数据库相关

**数据库名称**：`adaptive_eval`（注意不是 adaptive_exam）

**迁移脚本**：
- `migrate_simple.py` - 简化版，直接使用 pymysql
- `backend/scripts/migrate_add_question_id.py` - 完整版，使用 SQLAlchemy

**推荐使用**：`migrate_simple.py`（更简单，依赖更少）

### 配置文件

**`.env` 文件示例**：
```env
DEEPSEEK_API_KEY=sk-your-api-key
MYSQL_USER=root
MYSQL_PASSWORD=123456
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DB=adaptive_eval
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0
HF_ENDPOINT=https://hf-mirror.com
```

---

## 📊 项目大小统计

### 核心代码
- 后端代码：约 50 个文件
- 前端代码：约 10 个文件
- 总代码量：约 5000 行

### 数据文件
- 知识库文档：根据上传的文档数量
- FAISS 索引：约 10-50 MB
- 数据库：根据使用情况

### 依赖包
- Python 包：约 30 个（见 requirements.txt）
- 总大小：约 500 MB（包含模型文件）

---

## 🧹 清理建议

### 定期清理
```bash
# 运行清理脚本
conda activate FastAPI_env
python clean_project.py
```

### 手动清理
```bash
# 删除所有 __pycache__ 目录
find . -type d -name "__pycache__" -exec rm -rf {} +

# 删除所有 .pyc 文件
find . -type f -name "*.pyc" -delete

# 删除日志文件
find . -type f -name "*.log" -delete
```

### Git 清理
```bash
# 清理 Git 缓存
git rm -r --cached .
git add .
git commit -m "Clean up ignored files"
```

---

## 📦 打包建议

### 提交到 Git 时应包含
- ✅ 所有源代码文件
- ✅ requirements.txt
- ✅ README.md 和 DEVELOPMENT.md
- ✅ .gitignore
- ✅ 配置文件模板（不含敏感信息）
- ✅ 文档文件（notes/）

### 提交到 Git 时应排除
- ❌ .env（包含敏感信息）
- ❌ __pycache__/
- ❌ *.pyc
- ❌ data/app.db
- ❌ 虚拟环境目录
- ❌ 日志文件
- ❌ 临时文件

### 部署时需要
- ✅ 所有源代码
- ✅ requirements.txt
- ✅ .env（需要配置）
- ✅ 知识库文档（data/docs/）
- ❌ FAISS 索引（可以重新生成）
- ❌ 测试文件（可选）

---

## 🎯 最佳实践

1. **定期清理**：每周运行一次 `clean_project.py`
2. **备份数据**：定期备份数据库和知识库文档
3. **版本控制**：使用 Git 管理代码，不要提交敏感信息
4. **文档更新**：修改代码后及时更新文档
5. **环境隔离**：使用虚拟环境，不要污染全局 Python 环境

---

**最后更新**：2026-02-10

