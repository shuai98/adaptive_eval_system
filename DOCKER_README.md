# Docker 部署指南

## 快速开始

### 1. 准备工作

确保已安装 Docker 和 Docker Compose：
```bash
docker --version
docker-compose --version
```

### 2. 配置环境变量

将 `.env.docker` 重命名为 `.env`，并填写你的 DeepSeek API Key：
```bash
copy .env.docker .env
```

编辑 `.env` 文件：
```
DEEPSEEK_API_KEY=sk-your-actual-api-key
```

### 3. 启动服务

```bash
# 构建并启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f backend
```

### 4. 初始化数据库

等待服务启动后（约 30 秒），执行初始化脚本：

```bash
# 初始化数据库表
docker-compose exec backend python backend/scripts/init_db.py

# 创建管理员账号
docker-compose exec backend python backend/scripts/create_admin.py

# 初始化 RAG 向量库（如果需要）
docker-compose exec backend python backend/scripts/init_rag.py
```

### 5. 访问系统

- 登录页面: http://localhost:8088/static/login.html
- API 文档: http://localhost:8088/docs
- Agent 接口: http://localhost:8088/api/query

默认管理员账号：
- 用户名: admin
- 密码: 1234

## 常用命令

```bash
# 启动服务
docker-compose up -d

# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 查看日志
docker-compose logs -f backend

# 进入容器
docker-compose exec backend bash

# 重新构建镜像
docker-compose build --no-cache

# 清理所有数据（谨慎使用！）
docker-compose down -v
```

## 服务说明

### MySQL (端口 3306)
- 用户名: root
- 密码: 123456
- 数据库: adaptive_eval

### Redis (端口 6379)
- 无密码
- 数据库: 0

### 后端应用 (端口 8088)
- FastAPI 应用
- 自动重启

## 数据持久化

数据存储在 Docker volumes 中：
- `mysql_data`: MySQL 数据
- `redis_data`: Redis 数据
- `./data`: 文档和向量索引（挂载到宿主机）

## 故障排查

### 1. 服务启动失败
```bash
# 查看详细日志
docker-compose logs backend
```

### 2. 数据库连接失败
```bash
# 检查 MySQL 是否就绪
docker-compose exec mysql mysqladmin ping -h localhost -u root -p123456
```

### 3. 端口被占用
修改 `docker-compose.yml` 中的端口映射：
```yaml
ports:
  - "8089:8088"  # 改为其他端口
```

### 4. 重置所有数据
```bash
# 停止并删除所有容器和数据卷
docker-compose down -v

# 重新启动
docker-compose up -d
```

## 生产环境建议

1. 修改默认密码（MySQL、管理员账号）
2. 配置 HTTPS
3. 限制端口访问
4. 定期备份数据卷
5. 配置日志轮转

