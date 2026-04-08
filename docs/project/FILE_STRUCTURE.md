# 项目文件结构说明

## 核心目录

### `backend/`

后端主代码：

- `api/`：FastAPI 路由
- `core/`：配置、鉴权、日志与基础设施
- `db/`：数据库会话
- `models/`：SQLAlchemy 表定义
- `services/`：业务服务
- `scripts/`：初始化与维护脚本
- `main.py`：应用入口

### `frontend/`

当前前端采用双层结构：

- `app/`：当前正式使用的 Vue 3 SPA
- `common/`：浏览器端共享的会话与 API 工具
- `login.html`：兼容跳转页
- `student/index.html`：兼容跳转页
- `teacher/index.html`：兼容跳转页
- `admin/index.html`：兼容跳转页

说明：

- 真实页面实现已经集中到 `frontend/app`
- `frontend/student`、`frontend/teacher`、`frontend/admin` 不再承载旧原生前端逻辑，只保留跳转入口

### `data/`

运行数据与可再生产物：

- `docs/`：知识库文档
- `faiss_index/`：默认向量索引
- `faiss_index_eval_*`：评测索引产物
- `ragas_*.json|csv|md`：评测结果导出

### `docs/`

项目说明文档与开发文档。

### `tests/`

自动化测试。

### `notes/`

开发笔记和实验记录。

## 当前主要入口

- 根路由：`/`
- 主登录页：`/static/app/index.html#/login`
- 学生端：`/static/app/index.html#/student`
- 教师端：`/static/app/index.html#/teacher`
- 研发管理中心：`/static/app/index.html#/lab`

兼容跳转入口仍保留：

- `/static/login.html`
- `/static/student/index.html`
- `/static/teacher/index.html`
- `/static/admin/index.html`

## 重要脚本

- `backend/scripts/init_db.py`：初始化数据库
- `backend/scripts/create_admin.py`：创建管理员
- `backend/scripts/init_rag.py`：初始化知识索引
- `backend/scripts/migrate_add_question_id.py`：数据库迁移脚本
- `migrate_simple.py`：简化迁移脚本

## 可再生文件与清理建议

以下内容通常不应保留在仓库中：

- `__pycache__/`
- `pytest-cache-files-*`
- `.pytest_cache/`
- `.tmp_*`
- `*.log`
- 本地检查脚本和临时调试产物

如果出现这些文件，优先清理并通过 `.gitignore` 屏蔽。

## 维护原则

1. 新前端功能优先落在 `frontend/app`。
2. `frontend/common` 中的共享逻辑只保留被 SPA 使用的浏览器能力。
3. 兼容 HTML 页只负责跳转，不应继续承载业务逻辑。
4. 评测结果、缓存、索引和日志视为可再生产物，除非明确需要留档，否则不要长期堆在仓库里。
