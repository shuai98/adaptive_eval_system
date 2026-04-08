# 自适应评测系统

基于 FastAPI + RAG 的智能评测系统，支持学生答题、教师教学分析，以及研发侧的检索链路调试、RAGAS 评估和压力测试。

## 当前前端结构

- 主前端实现：`frontend/app`
- 共享浏览器工具：`frontend/common`
- 兼容入口页：`frontend/login.html`、`frontend/student/index.html`、`frontend/teacher/index.html`、`frontend/admin/index.html`

兼容入口页现在只负责跳转，实际使用路径统一为：

- 登录页：`/static/app/index.html#/login`
- 学生端：`/static/app/index.html#/student`
- 教师端：`/static/app/index.html#/teacher`
- 研发管理中心：`/static/app/index.html#/lab`

## 快速开始

### Docker 部署

```bash
copy env.docker .env
# 编辑 .env，填写必要配置

docker-compose up -d
docker-compose exec backend python backend/scripts/init_db.py
docker-compose exec backend python backend/scripts/create_admin.py
```

访问：

- 系统入口：`http://localhost:8088/static/app/index.html#/login`
- API 文档：`http://localhost:8088/docs`
- Agent 接口：`http://localhost:8088/api/query`

更多说明见 [DOCKER_README.md](DOCKER_README.md)。

### 本地开发

```bash
pip install -r requirements.txt
copy env.example .env
# 编辑 .env，填写必要配置

python backend/scripts/init_db.py
python backend/scripts/create_admin.py
python backend/main.py
```

## 项目结构

```text
adaptive_eval_system/
├── backend/              # FastAPI 后端
├── frontend/
│   ├── app/              # 当前 SPA 主前端
│   ├── common/           # 浏览器端共享会话与 API 工具
│   ├── admin/            # 兼容跳转页
│   ├── student/          # 兼容跳转页
│   ├── teacher/          # 兼容跳转页
│   └── login.html        # 兼容跳转页
├── data/                 # 文档、索引、评测产物
├── docs/                 # 项目文档
├── tests/                # 自动化测试
└── notes/                # 开发笔记
```

## 技术栈

- 后端：FastAPI、SQLAlchemy、MySQL、Redis
- 前端：Vue 3 SPA + Vue Router
- AI：LangChain、DeepSeek、FAISS、RAGAS
- 部署：Docker、Docker Compose

## 相关文档

- [Docker 部署指南](DOCKER_README.md)
- [Agent API 文档](docs/AGENT_API.md)
- [开发环境说明](docs/project/DEVELOPMENT.md)
- [文件结构说明](docs/project/FILE_STRUCTURE.md)

## 管理员初始化

`backend/scripts/create_admin.py` 会读取以下环境变量：

- `ADMIN_BOOTSTRAP_USERNAME`，默认 `root`
- `ADMIN_BOOTSTRAP_PASSWORD`，生产环境必须显式配置

研发管理中心仅允许 `root` 账号进入 `/lab` 路由。

## License

MIT
