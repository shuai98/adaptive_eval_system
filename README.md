# 基于大语言模型的个性化自适应测评系统

## 项目简介

本系统是一个基于大语言模型和 RAG 技术的智能测评平台，能够根据学生答题表现动态生成题目、智能评分，并自适应调整测评难度。系统支持选择题、简答题和场景题三种题型，教师可以上传自定义知识库，实现个性化的教学评估。

![系统架构图](./docs/images/architecture.png)
<!-- TODO: 添加系统架构图 -->

---

## 核心特性

- **动态题目生成**：基于 RAG 技术从知识库检索相关内容，结合 LLM 生成高质量题目
- **智能评分**：支持开放性问题的自动评分和评语生成
- **自适应难度调整**：根据学生答题情况动态调整题目难度
- **多题型支持**：选择题、简答题、场景应用题
- **知识库管理**：教师可上传 TXT 和 PDF 格式的教学资料
- **Rerank 优化**：使用 BGE-Reranker 提升检索精度
- **Redis 缓存**：相同关键词查询秒级响应

![系统界面展示](./docs/images/demo.png)
<!-- TODO: 添加系统界面截图 -->

---

## 技术架构

### 后端技术栈

- **框架**：FastAPI + Uvicorn（异步高性能）
- **大模型**：DeepSeek API
- **RAG 引擎**：LangChain + FAISS 向量库
- **Embedding 模型**：BGE-small-zh-v1.5
- **Rerank 模型**：BGE-Reranker-Base
- **数据库**：MySQL + Redis
- **ORM**：SQLAlchemy
- **文档加载**：PyPDFLoader + TextLoader

### 前端技术栈

- **框架**：Vue.js
- **界面**：原生 HTML/CSS/JavaScript

### 系统架构图

```
[前端] <--HTTP--> [后端 API]
                     |
        +------------+------------+
        |            |            |
    [LLM 服务]  [RAG 服务]   [数据库]
        |            |            |
    DeepSeek    FAISS+Rerank  MySQL+Redis
```

---

## 项目结构

```
adaptive_eval_system/
├── backend/                 # 后端代码
│   ├── api/                # API 路由
│   │   ├── admin.py       # 管理员接口
│   │   ├── student.py     # 学生接口
│   │   ├── teacher.py     # 教师接口
│   │   └── common.py      # 公共接口
│   ├── core/              # 核心配置
│   │   ├── config.py      # 配置文件
│   │   └── security.py    # 安全模块
│   ├── models/            # 数据模型
│   │   └── tables.py      # 数据库表定义
│   ├── services/          # 业务逻辑
│   │   ├── llm_service.py      # LLM 调用服务
│   │   ├── rag_service.py      # RAG 检索服务
│   │   └── metrics/            # 性能监控
│   ├── db/                # 数据库连接
│   └── main.py            # 启动入口
├── frontend/              # 前端代码
│   ├── login.html        # 登录页面
│   ├── student/          # 学生端
│   ├── teacher/          # 教师端
│   └── admin/            # 管理端
├── data/                  # 数据目录
│   ├── docs/             # 知识库文档
│   └── faiss_index/      # 向量索引
├── tests/                 # 测试文件
└── requirements.txt       # 依赖列表
```

---

## 快速开始

### 环境要求

- Python 3.9+
- MySQL 5.7+
- Redis 6.0+（可选，用于缓存加速）
- Conda（推荐）或 virtualenv

### 1. 克隆项目

```bash
git clone https://github.com/your-username/adaptive_eval_system.git
cd adaptive_eval_system
```

### 2. 创建并激活虚拟环境

**本项目使用的虚拟环境名称：`FastAPI_env`**

```bash
# 创建 Conda 环境
conda create -n FastAPI_env python=3.9

# 激活环境
conda activate FastAPI_env
```

> 💡 **提示**：详细的开发环境配置请查看 [DEVELOPMENT.md](./DEVELOPMENT.md)

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

在项目根目录创建 `.env` 文件：

```env
# DeepSeek API Key
DEEPSEEK_API_KEY=sk-your-api-key-here

# HuggingFace 镜像源（国内加速）
HF_ENDPOINT=https://hf-mirror.com
```

### 5. 初始化数据库

```bash
# 1. 在 MySQL 中创建数据库
CREATE DATABASE adaptive_eval CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

# 2. 运行初始化脚本（创建表结构）
conda activate FastAPI_env
python backend/scripts/init_db.py

# 3. 运行数据库迁移（添加 question_id 字段）
python migrate_simple.py
# 或者双击运行 run_migrate.bat
```

### 6. 初始化向量库

```bash
# 将教学资料放入 data/docs/ 目录，然后运行
python backend/scripts/init_rag.py
```

### 7. 启动 Redis

```bash
redis-server
```

### 8. 启动后端服务

```bash
conda activate FastAPI_env
python backend/main.py
```

或使用 uvicorn：

```bash
conda activate FastAPI_env
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8088
```

### 9. 访问系统

- 登录页面：http://127.0.0.1:8088/static/login.html
- API 文档：http://127.0.0.1:8088/docs

![登录界面](./docs/images/login.png)
<!-- TODO: 添加登录界面截图 -->

---

## 使用说明

### 教师端

1. **上传知识库**：支持 TXT 和 PDF 格式
2. **查看学生答题记录**：查看每个学生的做题情况和得分
3. **管理题目**：查看已生成的题目

![教师端界面](./docs/images/teacher.png)
<!-- TODO: 添加教师端截图 -->

### 学生端

1. **选择答题模式**：
   - 固定难度模式：手动选择简单/中等/困难
   - 自适应模式：系统根据答题表现自动调整难度
   
2. **选择题型**：
   - 选择题
   - 简答题
   - 场景应用题

3. **查看答案与解析**：提交后即时查看评分、正确答案和详细解析

![学生端界面](./docs/images/student.png)
<!-- TODO: 添加学生端截图 -->

### 管理端

- 查看系统性能指标
- 对比 RAG 不同配置的效果
- 查看 RAGAS 评估结果

---

## 核心功能说明

### RAG 检索流程

1. 用户输入关键词
2. 使用 BGE-Embedding 模型将关键词向量化
3. 在 FAISS 向量库中检索 Top-15 相关文档片段
4. 使用 BGE-Reranker 对结果重排序，取 Top-6
5. 从 Top-6 中随机选择 3 个片段作为上下文
6. 将上下文和关键词发送给 LLM 生成题目

![RAG 流程图](./docs/images/rag_flow.png)
<!-- TODO: 添加 RAG 流程图 -->

### 自适应算法

根据学生上一题的难度和得分决定下一题难度：

```
简单题 ≥ 80 分 → 升级到中等
中等题 ≥ 80 分 → 升级到困难
中等题 < 60 分 → 降级到简单
困难题 < 60 分 → 降级到中等
```

### 智能评分

使用 LLM 对开放性问题进行评分，评分维度：

- 准确性（40%）
- 完整性（30%）
- 逻辑性（30%）

返回：分数（0-100）、评分理由、改进建议

---

## 性能优化

### Redis 缓存策略

- 缓存相同关键词的检索结果
- TTL 设置为 1 小时
- 命中率提升约 60%，响应时间从 2.7s 降至 120ms

### 文档切分优化

使用 RecursiveCharacterTextSplitter：
- chunk_size: 500 字符
- chunk_overlap: 50 字符
- 分隔符优先级：`\n\n` > `\n` > `空格`

### 题目多样性优化

- Temperature 设置为 0.7（提高随机性）
- 从 Top-6 候选中随机选择 3 个作为上下文
- 避免相同关键词出现重复题目

---

## 配置说明

### 核心配置文件

`backend/core/config.py`

```python
# MySQL 配置
MYSQL_USER = "root"
MYSQL_PASSWORD = "your_password"
MYSQL_HOST = "127.0.0.1"
MYSQL_PORT = "3306"
MYSQL_DB = "adaptive_eval"

# Redis 配置
REDIS_HOST = "127.0.0.1"
REDIS_PORT = 6379
REDIS_DB = 0
```

### LLM 参数调优

`backend/services/llm_service.py`

```python
temperature = 0.7  # 控制输出随机性（0-1）
max_tokens = 2000  # 最大生成长度
```

---

## 开发说明

### 创建管理员账号

```bash
python backend/scripts/create_admin.py
```

### 测试 LLM 连接

```bash
python tests/test_llm.py
```

### 测试 RAG 检索

```bash
python tests/test_rag.py
```

### 测试 Redis 连接

```bash
python tests/test_redis_connection.py
```

---

## 已知问题

1. RAGAS 评估时 DeepSeek 不支持 `n > 1` 参数，需要修改 RAGAS 源码
2. 知识库更新需要手动重启服务才能生效（计划改进）
3. 流式输出尚未实现
4. 并发性能未进行压力测试

---

## 后续规划

- [ ] 实现流式输出，提升用户体验
- [ ] 添加知识库上传进度条
- [ ] 完成 RAGAS 自动化评测
- [ ] 使用 Locust 进行并发压力测试
- [ ] 探索混合搜索（Hybrid Search）
- [ ] Docker 容器化部署
- [ ] 集成知识图谱增强 RAG

---

## 贡献指南

欢迎提交 Issue 和 Pull Request。

---

## 开源协议

MIT License

---

## 联系方式

如有问题或建议，请通过以下方式联系：

- Email: your-email@example.com
- GitHub: https://github.com/your-username

---

## 致谢

- [LangChain](https://github.com/langchain-ai/langchain)
- [FastAPI](https://github.com/tiangolo/fastapi)
- [DeepSeek](https://www.deepseek.com/)
- [Datawhale](https://github.com/datawhalechina)

---

最后更新：2026-01-27
