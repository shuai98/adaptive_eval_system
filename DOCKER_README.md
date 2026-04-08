# Docker 部署指南

## 快速开始

### 1. 准备环境变量

```bash
copy env.docker .env
```

编辑 `.env`，至少补齐：

- `DEEPSEEK_API_KEY`
- `APP_SECRET_KEY`
- `MYSQL_PASSWORD`
- `ADMIN_BOOTSTRAP_PASSWORD`

### 2. 启动服务

```bash
docker-compose up -d
docker-compose logs -f backend
```

### 3. 初始化数据库与管理员

```bash
docker-compose exec backend python backend/scripts/init_db.py
docker-compose exec backend python backend/scripts/create_admin.py
docker-compose exec backend python backend/scripts/init_rag.py
```

### 4. 访问系统

- 主入口：`http://localhost:8088/static/app/index.html#/login`
- API 文档：`http://localhost:8088/docs`
- Agent 接口：`http://localhost:8088/api/query`

兼容跳转入口仍然保留：

- `http://localhost:8088/static/login.html`
- `http://localhost:8088/static/student/index.html`
- `http://localhost:8088/static/teacher/index.html`
- `http://localhost:8088/static/admin/index.html`

## 管理员说明

管理员创建脚本读取：

- `ADMIN_BOOTSTRAP_USERNAME`，默认 `root`
- `ADMIN_BOOTSTRAP_PASSWORD`

研发管理中心 `/lab` 仅允许 `root` 账号进入。

## 常用命令

```bash
docker-compose up -d
docker-compose down
docker-compose restart
docker-compose logs -f backend
docker-compose exec backend bash
docker-compose build --no-cache
docker-compose down -v
```

## 服务说明

### MySQL

- 端口：`3306`
- 用户：`root`
- 数据库：`adaptive_eval`

### Redis

- 端口：`6379`
- 数据库：`0`

### Backend

- 端口：`8088`
- FastAPI 应用

## 数据持久化

数据保存在 Docker volumes 和挂载目录中：

- `mysql_data`
- `redis_data`
- `./data`

## 故障排查

### 服务启动失败

```bash
docker-compose logs backend
```

### 数据库连接失败

```bash
docker-compose exec mysql mysqladmin ping -h localhost -u root -p123456
```

### 端口冲突

修改 `docker-compose.yml` 中的端口映射，例如：

```yaml
ports:
  - "8089:8088"
```

### 重置所有数据

```bash
docker-compose down -v
docker-compose up -d
```

## 生产环境建议

1. 配置强密码和正式密钥。
2. 为 FastAPI 前面增加反向代理与 HTTPS。
3. 限制对数据库和 Redis 端口的直接访问。
4. 定期备份数据库和 `data/` 目录。
5. 配置日志轮转与监控。
