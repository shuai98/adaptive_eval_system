# 工具脚本使用说明

本目录包含项目的各种工具脚本，用于初始化、迁移、测试等操作。

---

## 📂 脚本分类

### 🗄️ 数据库相关

#### `init_db.py` - 初始化数据库
**功能**: 创建数据库表结构

**使用方法**:
```bash
conda activate FastAPI_env
python backend/scripts/init_db.py
```

**注意事项**:
- 运行前确保 MySQL 服务已启动
- 需要先手动创建数据库: `CREATE DATABASE adaptive_eval`
- 会创建所有必要的表（用户、题目、答题记录等）

---

#### `migrate_add_question_id.py` - 数据库迁移
**功能**: 为 answers 表添加 question_id 字段

**使用方法**:
```bash
conda activate FastAPI_env
python backend/scripts/migrate_add_question_id.py
```

**注意事项**:
- 仅在需要添加 question_id 字段时运行
- 运行前会自动备份数据

---

#### `create_admin.py` - 创建管理员账号
**功能**: 创建系统管理员账号

**使用方法**:
```bash
conda activate FastAPI_env
python backend/scripts/create_admin.py
```

**交互流程**:
```
请输入管理员用户名: admin
请输入管理员密码: ******
请输入管理员邮箱: admin@example.com
✓ 管理员账号创建成功！
```

---

### 🔍 RAG 相关

#### `init_rag.py` - 初始化向量库
**功能**: 加载文档并构建 FAISS 向量索引

**使用方法**:
```bash
conda activate FastAPI_env
python backend/scripts/init_rag.py
```

**工作流程**:
1. 读取 `data/docs/` 目录下的所有文档（支持 TXT 和 PDF）
2. 使用 RecursiveCharacterTextSplitter 切分文档
3. 使用 BGE-small-zh-v1.5 模型生成向量
4. 构建 FAISS 索引并保存到 `data/faiss_index/`

**注意事项**:
- 首次运行会下载 Embedding 模型（约 100MB）
- 处理大量文档时可能需要较长时间
- 索引文件会保存为 `index.faiss` 和 `index.pkl`

---

### 🛠️ 项目工具

#### `clean_project.py` - 清理项目缓存
**功能**: 清理 Python 缓存文件和临时文件

**使用方法**:
```bash
python clean_project.py
```

**清理内容**:
- `__pycache__/` 目录
- `*.pyc` 文件
- `*.pyo` 文件
- `*.log` 日志文件

---

#### `pack_code.py` - 打包项目代码
**功能**: 将项目代码打包为 ZIP 文件

**使用方法**:
```bash
python pack_code.py
```

**打包内容**:
- 所有 Python 源代码
- 前端文件
- 配置文件
- 文档

**排除内容**:
- `__pycache__/` 缓存
- `data/` 数据文件
- `.env` 环境变量
- 虚拟环境

---

## 🚀 快速开始流程

### 首次部署

```bash
# 1. 激活虚拟环境
conda activate FastAPI_env

# 2. 创建数据库
mysql -u root -p
CREATE DATABASE adaptive_eval CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
exit

# 3. 初始化数据库表
python backend/scripts/init_db.py

# 4. 创建管理员账号
python backend/scripts/create_admin.py

# 5. 初始化向量库
python backend/scripts/init_rag.py

# 6. 启动服务
python backend/main.py
```

### 数据库迁移

```bash
# 运行迁移脚本
python backend/scripts/migrate_add_question_id.py

# 或使用批处理文件（Windows）
run_migrate.bat
```

### 更新知识库

```bash
# 1. 将新文档放入 data/docs/ 目录
# 2. 重新初始化向量库
python backend/scripts/init_rag.py

# 3. 重启服务
python backend/main.py
```

---

## ⚠️ 常见问题

### Q1: 运行脚本时提示找不到模块
**解决方法**:
```bash
# 确保已激活虚拟环境
conda activate FastAPI_env

# 确保在项目根目录运行
cd /d/BiShe_code/adaptive_eval_system
```

### Q2: 数据库连接失败
**解决方法**:
1. 检查 MySQL 服务是否启动
2. 检查 `.env` 文件中的数据库配置
3. 确认数据库已创建

### Q3: 向量库初始化失败
**解决方法**:
1. 检查 `data/docs/` 目录是否有文档
2. 确认网络连接正常（需要下载模型）
3. 检查磁盘空间是否充足

### Q4: Redis 连接失败
**解决方法**:
```bash
# 启动 Redis 服务
redis-server

# 或者在配置中禁用 Redis（系统会自动降级）
```

---

## 📝 脚本开发规范

如果需要添加新的工具脚本，请遵循以下规范：

1. **命名规范**: 使用小写字母和下划线，如 `init_xxx.py`
2. **文档注释**: 在文件开头添加功能说明
3. **错误处理**: 添加适当的异常处理和提示信息
4. **日志输出**: 使用清晰的日志输出，便于调试
5. **更新文档**: 在本 README 中添加使用说明

---

**最后更新**: 2026-03-03

