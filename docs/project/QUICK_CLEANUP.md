# 项目整理快速指南

本文档提供了快速整理项目结构的步骤和命令。

---

## 📋 整理清单

### ✅ 已完成
- [x] 创建 `PROJECT_STRUCTURE.md` - 项目结构文档
- [x] 创建 `.gitignore` - Git 忽略文件
- [x] 创建 `env.example` - 环境变量模板
- [x] 创建 `scripts/README.md` - 脚本使用说明

### 🔲 可选整理（根据需要执行）
- [ ] 移动根目录脚本文件到 `backend/scripts/`
- [ ] 整理 `notes/` 目录结构
- [ ] 删除临时文件
- [ ] 清理 Python 缓存

---

## 🚀 快速整理命令

### 方案一：保守整理（推荐）

只做最基础的清理，不移动文件：

```bash
# 1. 清理 Python 缓存
python clean_project.py

# 2. 删除临时文件（可选）
# del project_context.txt
```

### 方案二：完整整理

如果你想彻底整理项目结构：

#### Step 1: 移动根目录脚本到 backend/scripts/

```bash
# Windows PowerShell
move migrate_simple.py backend\scripts\
move update_db.py backend\scripts\
```

#### Step 2: 整理笔记目录

```bash
# 创建子目录
mkdir notes\development
mkdir notes\experiment
mkdir notes\presentation
mkdir notes\images

# 移动开发笔记
move notes\00_项目概述.md notes\development\
move notes\01_技术选型.md notes\development\
move notes\02_系统设计.md notes\development\
move notes\03_实现过程.md notes\development\
move notes\04_问题与Bug.md notes\development\

# 移动实验记录
move notes\05_实验与结果.md notes\experiment\

# 移动答辩准备
move notes\06_答辩准备.md notes\presentation\
move notes\07_自适应可视化功能.md notes\presentation\

# 移动图片（MyNote 文件夹内的所有图片）
move notes\MyNote\*.png notes\images\
move notes\MyNote\*.md notes\
rmdir notes\MyNote
```

#### Step 3: 移动其他文件

```bash
# 移动笔记
move My_note.md notes\

# 移动文档
move README.pdf docs\
```

#### Step 4: 删除临时文件

```bash
# 删除临时文件
del project_context.txt
```

#### Step 5: 清理缓存

```bash
# 运行清理脚本
python clean_project.py
```

---

## 📁 整理后的目录结构

```
adaptive_eval_system/
│
├── backend/                    # 后端代码
│   ├── api/                   # ✅ 结构良好
│   ├── core/                  # ✅ 结构良好
│   ├── db/                    # ✅ 结构良好
│   ├── models/                # ✅ 结构良好
│   ├── services/              # ✅ 结构良好
│   ├── scripts/               # ✅ 所有脚本集中管理
│   │   ├── create_admin.py
│   │   ├── init_db.py
│   │   ├── init_rag.py
│   │   ├── migrate_add_question_id.py
│   │   ├── migrate_simple.py  # 新移入
│   │   ├── update_db.py       # 新移入
│   │   └── README.md          # 新增
│   └── main.py
│
├── frontend/                   # ✅ 结构良好
│
├── data/                       # ✅ 结构良好
│
├── docs/                       # 📝 文档集中管理
│   ├── AGENT_API.md           # Agent API 文档
│   └── README.pdf             # 新移入
│
├── notes/                      # 📝 笔记分类管理
│   ├── development/           # 开发笔记
│   │   ├── 00_项目概述.md
│   │   ├── 01_技术选型.md
│   │   ├── 02_系统设计.md
│   │   ├── 03_实现过程.md
│   │   └── 04_问题与Bug.md
│   ├── experiment/            # 实验记录
│   │   └── 05_实验与结果.md
│   ├── presentation/          # 答辩准备
│   │   ├── 06_答辩准备.md
│   │   └── 07_自适应可视化功能.md
│   ├── images/                # 统一图片目录
│   │   └── (所有图片)
│   └── My_note.md             # 新移入
│
├── scripts/                    # 🛠️ 项目工具脚本
│   ├── clean_project.py
│   ├── pack_code.py
│   └── README.md              # 新增
│
├── tests/                      # ✅ 结构良好
│
├── .gitignore                  # 新增
├── env.example                 # 新增
├── requirements.txt
├── README.md
├── DEVELOPMENT.md
├── FILE_STRUCTURE.md
├── PROJECT_STRUCTURE.md        # 新增
├── QUICK_CLEANUP.md            # 本文件
└── run_migrate.bat
```

---

## ⚠️ 注意事项

### 移动文件前的检查

1. **确保没有正在运行的进程**
   - 关闭所有使用这些文件的程序
   - 停止后端服务

2. **备份重要文件**（可选）
   ```bash
   # 创建备份
   mkdir backup
   copy migrate_simple.py backup\
   copy update_db.py backup\
   ```

3. **检查文件引用**
   - `run_migrate.bat` 可能引用了 `migrate_simple.py`
   - 如果移动文件，需要更新批处理文件中的路径

### 移动后需要更新的文件

如果你移动了 `migrate_simple.py`，需要更新 `run_migrate.bat`：

```batch
@echo off
echo ====================================
echo 数据库迁移工具
echo ====================================
echo.

REM 激活虚拟环境
call conda activate FastAPI_env

REM 运行迁移脚本（更新路径）
python backend\scripts\migrate_simple.py

echo.
echo 迁移完成！
pause
```

---

## 🎯 推荐方案

### 对于正在开发的项目（推荐）

**只做基础清理，不移动文件**：

```bash
# 1. 清理缓存
python clean_project.py

# 2. 使用新增的文档
# - 查看 PROJECT_STRUCTURE.md 了解项目结构
# - 查看 scripts/README.md 了解脚本用法
# - 参考 env.example 配置环境变量
```

**优点**：
- ✅ 不影响现有代码和脚本
- ✅ 风险最小
- ✅ 可以继续正常开发

### 对于准备交付的项目

**完整整理**：

按照"方案二：完整整理"的步骤执行，让项目结构更加规范。

**优点**：
- ✅ 结构更清晰
- ✅ 更符合最佳实践
- ✅ 便于他人理解

**注意**：
- ⚠️ 需要更新相关引用
- ⚠️ 建议先备份

---

## 📊 整理效果对比

### 整理前
```
根目录: 15+ 个文件（混乱）
notes/: 8 个 md + 50+ 张图片（混乱）
__pycache__/: 到处都是（占用空间）
```

### 整理后
```
根目录: 10 个文件（清晰）
notes/: 按类型分类（清晰）
__pycache__/: 已清理（节省空间）
```

---

## 🔍 验证整理结果

整理完成后，运行以下命令验证：

```bash
# 1. 测试后端启动
python backend/main.py

# 2. 测试数据库脚本
python backend/scripts/init_db.py --help

# 3. 测试 RAG 脚本
python backend/scripts/init_rag.py --help

# 4. 运行测试
python tests/test_llm.py
```

如果所有测试都通过，说明整理成功！✅

---

## 💡 日常维护建议

### 定期清理（每周）
```bash
python clean_project.py
```

### 更新知识库（按需）
```bash
python backend/scripts/init_rag.py
```

### 备份重要数据（每月）
```bash
# 备份数据库
mysqldump -u root -p adaptive_eval > backup_$(date +%Y%m%d).sql

# 备份向量库
python scripts/pack_code.py
```

---

**创建时间**: 2026-03-03  
**适用版本**: V1.0.0

