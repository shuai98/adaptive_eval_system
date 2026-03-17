# 项目结构整理文档

## 📁 当前项目结构

```
adaptive_eval_system/
│
├── 📂 backend/                    # 后端核心代码
│   ├── api/                       # API 路由层
│   │   ├── admin.py              # 管理员接口
│   │   ├── agent.py              # Agent 对接接口 ⭐ 新增
│   │   ├── common.py             # 公共接口
│   │   ├── router.py             # 路由汇总
│   │   ├── student.py            # 学生接口
│   │   └── teacher.py            # 教师接口
│   │
│   ├── core/                      # 核心配置
│   │   ├── config.py             # 配置文件
│   │   ├── events.py             # 事件处理
│   │   └── security.py           # 安全模块
│   │
│   ├── db/                        # 数据库层
│   │   └── session.py            # 数据库会话
│   │
│   ├── models/                    # 数据模型
│   │   └── tables.py             # 数据库表定义
│   │
│   ├── services/                  # 业务逻辑层
│   │   ├── metrics/              # 性能监控模块
│   │   │   ├── locustfile.py    # 压力测试
│   │   │   ├── ragas_service.py # RAGAS 评估
│   │   │   ├── stress_service.py # 压测服务
│   │   │   └── timer.py          # 计时工具
│   │   ├── llm_service.py        # LLM 调用服务
│   │   └── rag_service.py        # RAG 检索服务
│   │
│   ├── scripts/                   # 工具脚本
│   │   ├── create_admin.py       # 创建管理员
│   │   ├── init_db.py            # 初始化数据库
│   │   ├── init_rag.py           # 初始化向量库
│   │   └── migrate_add_question_id.py  # 数据库迁移
│   │
│   └── main.py                    # 应用入口 ⭐ 核心文件
│
├── 📂 frontend/                   # 前端代码
│   ├── admin/                     # 管理端
│   │   └── index.html
│   ├── student/                   # 学生端
│   │   ├── css/
│   │   │   └── main.css
│   │   ├── js/
│   │   │   └── app.js
│   │   └── index.html
│   ├── teacher/                   # 教师端
│   │   └── index.html
│   └── login.html                 # 登录页面
│
├── 📂 data/                       # 数据目录
│   ├── docs/                      # 知识库文档
│   │   ├── db.txt
│   │   ├── 流畅的python.pdf
│   │   └── 网络爬虫－Python和数据分析.pdf
│   ├── faiss_index/              # 向量索引
│   │   ├── index.faiss
│   │   └── index.pkl
│   └── golden_dataset.json       # 评估数据集
│
├── 📂 docs/                       # 项目文档
│   └── AGENT_API.md              # Agent API 文档 ⭐ 新增
│
├── 📂 notes/                      # 开发笔记（建议整理）
│   ├── MyNote/                    # 个人笔记（图片较多）
│   ├── 00_项目概述.md
│   ├── 01_技术选型.md
│   ├── 02_系统设计.md
│   ├── 03_实现过程.md
│   ├── 04_问题与Bug.md
│   ├── 05_实验与结果.md
│   ├── 06_答辩准备.md
│   └── 07_自适应可视化功能.md
│
├── 📂 tests/                      # 测试文件
│   ├── test_adaptive_stats.py    # 自适应统计测试
│   ├── test_agent_api.py         # Agent API 测试 ⭐ 新增
│   ├── test_grade.py             # 评分测试
│   ├── test_llm.py               # LLM 连接测试
│   ├── test_rag.py               # RAG 检索测试
│   ├── test_redis_connection.py  # Redis 连接测试
│   └── test_rerank.py            # Rerank 测试
│
├── 📄 配置与工具文件
│   ├── .env                       # 环境变量（需创建）
│   ├── requirements.txt           # Python 依赖
│   ├── README.md                  # 项目说明
│   ├── DEVELOPMENT.md             # 开发指南
│   ├── FILE_STRUCTURE.md          # 文件结构说明
│   ├── PROJECT_STRUCTURE.md       # 本文件 ⭐ 新增
│   │
│   ├── migrate_simple.py          # 数据库迁移脚本
│   ├── run_migrate.bat            # 迁移批处理
│   ├── update_db.py               # 数据库更新
│   ├── clean_project.py           # 项目清理工具
│   └── pack_code.py               # 代码打包工具
│
└── 📄 临时/生成文件（可忽略）
    ├── __pycache__/               # Python 缓存
    ├── My_note.md                 # 临时笔记
    ├── project_context.txt        # 项目上下文
    └── README.pdf                 # README PDF 版本
```

---

## 🎯 项目结构优化建议

### 1. 需要整理的部分

#### ❌ 根目录文件过多
**问题**：根目录有太多零散文件，不够清晰

**建议整理**：
```
当前根目录文件：
- migrate_simple.py
- update_db.py
- clean_project.py
- pack_code.py
- My_note.md
- project_context.txt
- README.pdf

建议移动到：
📂 scripts/          # 工具脚本
  ├── migrate_simple.py
  ├── update_db.py
  ├── clean_project.py
  └── pack_code.py

📂 notes/            # 笔记文档
  └── My_note.md

📂 docs/             # 文档
  └── README.pdf

可删除：
  └── project_context.txt  # 临时文件
```

#### ❌ notes/ 目录结构混乱
**问题**：MyNote 文件夹有 50+ 张图片，与其他 markdown 文件混在一起

**建议整理**：
```
📂 notes/
  ├── 📂 development/          # 开发笔记
  │   ├── 00_项目概述.md
  │   ├── 01_技术选型.md
  │   ├── 02_系统设计.md
  │   ├── 03_实现过程.md
  │   └── 04_问题与Bug.md
  │
  ├── 📂 experiment/           # 实验记录
  │   └── 05_实验与结果.md
  │
  ├── 📂 presentation/         # 答辩准备
  │   ├── 06_答辩准备.md
  │   └── 07_自适应可视化功能.md
  │
  └── 📂 images/               # 统一图片目录
      └── (所有图片文件)
```

#### ❌ __pycache__ 缓存文件
**问题**：Python 缓存文件被提交到版本控制

**建议**：创建 `.gitignore` 文件

---

### 2. 建议新增的文件

#### ✅ .gitignore（版本控制忽略文件）
```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# 环境变量
.env
.venv
env/
venv/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo

# 数据文件
data/docs/*.pdf
data/faiss_index/

# 日志
*.log

# 临时文件
*.tmp
project_context.txt
```

#### ✅ .env.example（环境变量模板）
```env
# DeepSeek API Key
DEEPSEEK_API_KEY=sk-your-api-key-here

# HuggingFace 镜像源
HF_ENDPOINT=https://hf-mirror.com

# MySQL 配置
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DB=adaptive_eval

# Redis 配置
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0
```

#### ✅ scripts/README.md（脚本使用说明）
```markdown
# 工具脚本说明

## 数据库相关
- `init_db.py` - 初始化数据库表结构
- `migrate_simple.py` - 数据库迁移（添加 question_id）
- `update_db.py` - 数据库更新工具
- `create_admin.py` - 创建管理员账号

## RAG 相关
- `init_rag.py` - 初始化向量库

## 项目工具
- `clean_project.py` - 清理项目缓存文件
- `pack_code.py` - 打包项目代码
```

---

### 3. 推荐的目录结构（最佳实践）

```
adaptive_eval_system/
│
├── 📂 backend/              # 后端（保持不变，结构很好）
├── 📂 frontend/             # 前端（保持不变）
├── 📂 data/                 # 数据（保持不变）
│
├── 📂 docs/                 # 📝 所有文档集中管理
│   ├── api/                 # API 文档
│   │   └── AGENT_API.md
│   ├── development/         # 开发文档
│   │   └── DEVELOPMENT.md
│   ├── architecture/        # 架构设计
│   │   └── FILE_STRUCTURE.md
│   └── README.pdf
│
├── 📂 notes/                # 📝 开发笔记（按类型分类）
│   ├── development/
│   ├── experiment/
│   ├── presentation/
│   └── images/
│
├── 📂 scripts/              # 🛠️ 所有工具脚本
│   ├── database/            # 数据库脚本
│   ├── rag/                 # RAG 相关脚本
│   └── utils/               # 通用工具
│
├── 📂 tests/                # ✅ 测试（保持不变，结构很好）
│
├── 📄 .env.example          # 环境变量模板
├── 📄 .gitignore            # Git 忽略文件
├── 📄 requirements.txt      # 依赖列表
├── 📄 README.md             # 项目说明
└── 📄 PROJECT_STRUCTURE.md  # 本文件
```

---

## 🚀 快速整理步骤

### 第一步：创建 .gitignore
```bash
# 在项目根目录创建 .gitignore 文件
# 内容见上方建议
```

### 第二步：清理缓存文件
```bash
# 运行清理脚本
python clean_project.py
```

### 第三步：整理根目录文件（可选）
```bash
# 移动脚本文件到 scripts/
move migrate_simple.py backend/scripts/
move update_db.py backend/scripts/

# 移动笔记到 notes/
move My_note.md notes/

# 移动文档到 docs/
move README.pdf docs/
```

### 第四步：整理 notes/ 目录（可选）
```bash
# 创建子目录
mkdir notes/development
mkdir notes/experiment
mkdir notes/presentation
mkdir notes/images

# 移动文件（根据类型）
move notes/00_*.md notes/development/
move notes/01_*.md notes/development/
# ... 以此类推
```

---

## 📊 项目统计

### 代码结构
- **后端文件**: 20+ 个 Python 文件
- **前端文件**: 4 个 HTML 页面 + CSS/JS
- **测试文件**: 7 个测试脚本
- **文档文件**: 10+ 个 Markdown 文档

### 核心模块
1. **API 层**: 6 个路由文件（含新增的 agent.py）
2. **服务层**: 2 个核心服务 + 性能监控模块
3. **数据层**: MySQL + Redis + FAISS

### 技术栈
- **后端**: FastAPI + LangChain + SQLAlchemy
- **前端**: 原生 HTML/CSS/JavaScript
- **AI**: DeepSeek + BGE Embedding + BGE Reranker
- **数据库**: MySQL + Redis + FAISS

---

## 💡 维护建议

### 日常开发
1. ✅ 新增 API 接口 → `backend/api/`
2. ✅ 新增业务逻辑 → `backend/services/`
3. ✅ 新增测试 → `tests/`
4. ✅ 新增文档 → `docs/`

### 代码规范
1. 使用 `.gitignore` 避免提交缓存文件
2. 环境变量统一放在 `.env` 文件
3. 工具脚本统一放在 `scripts/` 目录
4. 文档按类型分类存放

### 版本控制
1. 定期清理 `__pycache__` 缓存
2. 大文件（PDF、模型）不要提交到 Git
3. 敏感信息（API Key）使用 `.env` 管理

---

## 📌 重要文件说明

### 必读文档
1. `README.md` - 项目总览和快速开始
2. `DEVELOPMENT.md` - 开发环境配置
3. `docs/AGENT_API.md` - Agent 接口文档
4. `PROJECT_STRUCTURE.md` - 本文件（项目结构）

### 核心代码
1. `backend/main.py` - 应用入口
2. `backend/services/rag_service.py` - RAG 核心逻辑
3. `backend/services/llm_service.py` - LLM 调用
4. `backend/api/agent.py` - Agent 对接接口

### 工具脚本
1. `backend/scripts/init_db.py` - 初始化数据库
2. `backend/scripts/init_rag.py` - 初始化向量库
3. `backend/scripts/create_admin.py` - 创建管理员

---

**最后更新**: 2026-03-03
**维护者**: 项目开发团队

