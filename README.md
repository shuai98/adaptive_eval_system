# 自适应测评系统

基于 FastAPI + LangChain + RAG 的智能测评系统，支持自适应出题和智能评分。

## 📁 项目结构

```
adaptive_eval_system/
├── backend/              # 后端代码
│   ├── api/             # API 路由
│   ├── core/            # 核心配置
│   ├── db/              # 数据库
│   ├── models/          # 数据模型
│   ├── services/        # 业务逻辑
│   ├── scripts/         # 初始化脚本
│   └── main.py          # 入口文件
├── frontend/            # 前端页面
│   ├── admin/          # 管理员界面
│   ├── student/        # 学生界面
│   ├── teacher/        # 教师界面
│   └── login.html      # 登录页
├── data/               # 数据目录
│   ├── docs/          # 文档库
│   └── faiss_index/   # 向量索引
├── docs/              # 项目文档
├── scripts/           # 工具脚本
│   └── dev/          # 开发脚本
├── tests/            # 测试代码
└── notes/            # 开发笔记

```

## 🚀 快速开始

### 方式一：Docker 部署（推荐）

```bash
# 1. 配置环境变量
copy env.docker .env
# 编辑 .env 填入 DEEPSEEK_API_KEY

# 2. 启动服务
docker-compose up -d

# 3. 初始化数据库
docker-compose exec backend python backend/scripts/init_db.py
docker-compose exec backend python backend/scripts/create_admin.py

# 4. 访问系统
# http://localhost:8088/static/login.html
```

详细说明见 [DOCKER_README.md](DOCKER_README.md)

### 方式二：本地开发

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
copy env.example .env
# 编辑 .env 填入配置

# 3. 初始化数据库
python backend/scripts/init_db.py
python backend/scripts/create_admin.py

# 4. 启动服务
python backend/main.py
```

## 📚 文档

- [Docker 部署指南](DOCKER_README.md)
- [API 文档](docs/AGENT_API.md)
- [开发文档](docs/project/)

## 🛠️ 技术栈

- **后端**: FastAPI + SQLAlchemy + MySQL
- **AI**: LangChain + DeepSeek + FAISS
- **前端**: 原生 HTML/CSS/JS
- **部署**: Docker + Docker Compose

## 📝 默认账号

- 用户名: `admin`
- 密码: `admin123`

## 📄 License

MIT
