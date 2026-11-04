# BidPivot 部署指南

本文档为 BidPivot（极智标枢-标书智造平台）的完整部署指南，涵盖 Docker Compose 快速部署、手动部署、Kubernetes 生产部署等多种方式。

---

## 目录

1. [环境要求](#1-环境要求)
2. [Docker Compose 部署（推荐）](#2-docker-compose-部署推荐)
3. [手动部署](#3-手动部署)
4. [Kubernetes 部署](#4-kubernetes-部署)
5. [环境变量说明](#5-环境变量说明)
6. [数据库迁移](#6-数据库迁移)
7. [SSL 证书配置](#7-ssl-证书配置)
8. [常见问题](#8-常见问题)

---

## 1. 环境要求

### 基础环境

| 组件 | 最低版本 | 推荐版本 | 说明 |
|------|---------|---------|------|
| Python | 3.11+ | 3.11.x | 后端运行环境 |
| Node.js | 18+ | 20 LTS | 前端构建环境 |
| Docker | 24+ | 25+ | 容器化部署 |
| Docker Compose | 2.20+ | 2.24+ | 多容器编排 |
| PostgreSQL | 15+ | 16.x | 关系型数据库 |
| Redis | 7+ | 7.2+ | 任务队列与缓存 |
| Qdrant | 1.7+ | 1.9+ | 向量数据库 |
| MinIO | 最新稳定版 | - | 文件存储 |

### 可选组件

| 组件 | 用途 |
|------|------|
| Nginx | 反向代理、静态资源托管、SSL 终结 |
| Celery | 异步任务队列 Worker |
| Electron | 桌面端封装（Phase 3） |

### 硬件建议

| 环境 | CPU | 内存 | 磁盘 |
|------|-----|------|------|
| 开发/测试 | 4 核 | 8 GB | 50 GB SSD |
| 生产环境 | 8 核+ | 16 GB+ | 200 GB+ SSD |

> **注意**：如果使用本地大模型（如 Ollama），建议至少 16 GB 内存 + 独立 GPU。

---

## 2. Docker Compose 部署（推荐）

### 2.1 克隆项目

```bash
git clone https://github.com/your-org/BidPivot.git
cd BidPivot
```

### 2.2 配置环境变量

复制环境变量模板：

```bash
cp .env.example .env
```

编辑 `.env` 文件，**必须修改**以下变量：

```bash
# ===== 必须修改 =====
POSTGRES_PASSWORD=your_secure_db_password_here
MINIO_ROOT_PASSWORD=your_secure_minio_password_here
SECRET_KEY=your_random_secret_key_at_least_32_chars
JWT_SECRET_KEY=your_random_jwt_secret_key

# ===== LLM 配置（二选一）=====
# 云端大模型
LLM_PROVIDER=openai
LLM_API_KEY=sk-your-api-key-here
LLM_MODEL_NAME=gpt-4o

# 或本地大模型（Ollama）
# LLM_PROVIDER=ollama
# LLM_BASE_URL=http://host.docker.internal:11434
# LLM_MODEL_NAME=qwen2.5:14b

# ===== 可选修改 =====
POSTGRES_USER=bidpivot
POSTGRES_DB=bidpivot
REDIS_URL=redis://redis:6379/0
QDRANT_URL=http://qdrant:6333
MINIO_ENDPOINT=minio:9000
```

生成安全密钥的快捷方式：

```bash
# 生成 SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(48))"
# 生成 JWT_SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 2.3 启动服务

```bash
# 启动所有服务（后台运行）
docker-compose up -d

# 查看启动状态
docker-compose ps

# 查看实时日志
docker-compose logs -f

# 仅查看特定服务日志
docker-compose logs -f backend
docker-compose logs -f celery-worker
```

### 2.4 验证部署

等待所有容器启动完成后（首次启动约 2-5 分钟），逐一验证：

```bash
# 1. 检查所有容器状态（应全部为 Up/healthy）
docker-compose ps

# 2. 验证后端 API
curl http://localhost:8000/health
# 期望返回: {"status": "ok"}

# 3. 验证前端页面
curl -I http://localhost:3000
# 期望返回: HTTP/1.1 200 OK

# 4. 验证 PostgreSQL
docker-compose exec postgres psql -U bidpivot -d bidpivot -c "SELECT 1;"
# 期望返回: 1 row

# 5. 验证 Redis
docker-compose exec redis redis-cli ping
# 期望返回: PONG

# 6. 验证 Qdrant
curl http://localhost:6333/healthz
# 期望返回: healthz check passed

# 7. 验证 MinIO
curl -I http://localhost:9000/minio/health/live
# 期望返回: HTTP/1.1 200 OK
```

### 2.5 开发环境覆盖配置

开发环境可使用 `docker-compose.override.yml` 覆盖默认配置（如挂载源码目录、开启热重载）：

```bash
# 使用开发覆盖配置启动
docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d
```

### 2.6 停止与清理

```bash
# 停止所有服务（保留数据卷）
docker-compose down

# 停止并删除数据卷（危险！会清除所有数据）
docker-compose down -v

# 停止并删除所有内容（包括镜像）
docker-compose down -v --rmi all
```

---

## 3. 手动部署

适用于需要精细控制服务配置的场景，或无法使用 Docker 的环境。

### 3.1 后端部署

#### 3.1.1 创建虚拟环境

```bash
cd backend
python -m venv venv

# Linux/macOS
source venv/bin/activate

# Windows
venv\Scripts\activate
```

#### 3.1.2 安装依赖

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### 3.1.3 数据库初始化

```bash
# 确保 PostgreSQL 已启动并创建数据库
psql -U postgres -c "CREATE DATABASE bidpivot;"
psql -U postgres -c "CREATE USER bidpivot WITH PASSWORD 'your_password';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE bidpivot TO bidpivot;"

# 执行数据库迁移
alembic upgrade head
```

#### 3.1.4 创建管理员账户

```bash
python -m app.scripts.create_admin
```

#### 3.1.5 启动后端服务

```bash
# 开发模式（自动重载）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 生产模式（推荐使用 Gunicorn + Uvicorn Worker）
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
```

> **建议**：生产环境使用 `systemd` 或 `supervisor` 管理进程，确保服务自动重启。

**systemd 服务文件示例** (`/etc/systemd/system/bidpivot-backend.service`):

```ini
[Unit]
Description=BidPivot Backend Service
After=network.target postgresql.service redis.service

[Service]
Type=exec
User=bidpivot
Group=bidpivot
WorkingDirectory=/opt/BidPivot/backend
Environment="PATH=/opt/BidPivot/backend/venv/bin"
ExecStart=/opt/BidPivot/backend/venv/bin/gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 127.0.0.1:8000 \
  --timeout 120
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable bidpivot-backend
sudo systemctl start bidpivot-backend
sudo systemctl status bidpivot-backend
```

### 3.2 前端部署

#### 3.2.1 安装依赖并构建

```bash
cd frontend
npm install

# 配置 API 地址（可选，默认为 /api 由 Nginx 代理）
echo "VITE_API_BASE_URL=http://localhost:8000" > .env.production

# 构建生产版本
npm run build
```

构建产物输出到 `frontend/dist/` 目录。

#### 3.2.2 Nginx 配置

安装 Nginx：

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install -y nginx

# CentOS/RHEL
sudo yum install -y nginx
```

创建站点配置 (`/etc/nginx/conf.d/bidpivot.conf`):

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 重定向到 HTTPS（生产环境）
    # return 301 https://$host$request_uri;

    # 前端静态资源
    root /opt/BidPivot/frontend/dist;
    index index.html;

    # SPA 路由回退
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API 反向代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 请求体大小限制（文件上传）
        client_max_body_size 100M;

        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }

    # WebSocket 代理
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 86400s;
    }

    # 静态资源缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2?)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # 安全头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
```

验证并重载 Nginx：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 3.3 Celery Worker 部署

Celery Worker 负责执行异步的标书生成任务（LangGraph 多 Agent 流水线）。

```bash
# 确保在 backend 虚拟环境中
cd backend
source venv/bin/activate

# 启动 Celery Worker
celery -A app.celery worker \
  --loglevel=info \
  --concurrency=4 \
  --max-tasks-per-child=100 \
  -Q default,generation

# 启动 Celery Beat（定时任务调度器，可选）
celery -A app.celery beat --loglevel=info
```

**systemd 服务文件示例** (`/etc/systemd/system/bidpivot-celery.service`):

```ini
[Unit]
Description=BidPivot Celery Worker
After=network.target redis.service

[Service]
Type=exec
User=bidpivot
Group=bidpivot
WorkingDirectory=/opt/BidPivot/backend
Environment="PATH=/opt/BidPivot/backend/venv/bin"
ExecStart=/opt/BidPivot/backend/venv/bin/celery -A app.celery worker \
  --loglevel=info \
  --concurrency=4 \
  --max-tasks-per-child=100 \
  -Q default,generation
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable bidpivot-celery
sudo systemctl start bidpivot-celery
```

### 3.4 依赖服务配置

#### PostgreSQL

```bash
# 安装
sudo apt install -y postgresql-15

# 配置远程访问（编辑 /etc/postgresql/15/main/postgresql.conf）
# listen_addresses = '*'

# 配置认证（编辑 /etc/postgresql/15/main/pg_hba.conf）
# host  bidpivot  bidpivot  0.0.0.0/0  md5

sudo systemctl restart postgresql
```

#### Redis

```bash
# 安装
sudo apt install -y redis-server

# 配置（编辑 /etc/redis/redis.conf）
# requirepass your_redis_password
# maxmemory 2gb
# maxmemory-policy allkeys-lru

sudo systemctl restart redis-server
```

#### Qdrant

```bash
# 使用 Docker 运行
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -v /opt/qdrant/storage:/qdrant/storage \
  qdrant/qdrant:latest

# 或使用 systemd 管理（二进制安装）
# 参考 https://qdrant.tech/documentation/quick-start/
```

#### MinIO

```bash
# 使用 Docker 运行
docker run -d \
  --name minio \
  -p 9000:9000 \
  -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=your_minio_password \
  -v /opt/minio/data:/data \
  minio/minio server /data --console-address ":9001"
```

---

## 4. Kubernetes 部署

适用于生产环境的高可用部署方案。

### 4.1 前置条件

- Kubernetes 集群（1.27+）
- kubectl 已配置并可访问集群
- Helm 3（可选，用于安装依赖组件）
- 集群中已安装 Ingress Controller（如 nginx-ingress）

### 4.2 创建命名空间

```bash
kubectl create namespace bidpivot
```

### 4.3 配置 Secrets

```bash
# 创建数据库密码 Secret
kubectl create secret generic bidpivot-db-secret \
  --namespace bidpivot \
  --from-literal=POSTGRES_PASSWORD=your_secure_db_password \
  --from-literal=POSTGRES_USER=bidpivot \
  --from-literal=POSTGRES_DB=bidpivot

# 创建应用密钥 Secret
kubectl create secret generic bidpivot-app-secret \
  --namespace bidpivot \
  --from-literal=SECRET_KEY=your_random_secret_key \
  --from-literal=JWT_SECRET_KEY=your_random_jwt_secret \
  --from-literal=LLM_API_KEY=sk-your-api-key

# 创建 MinIO 密码 Secret
kubectl create secret generic bidpivot-minio-secret \
  --namespace bidpivot \
  --from-literal=MINIO_ROOT_USER=minioadmin \
  --from-literal=MINIO_ROOT_PASSWORD=your_minio_password

# 验证 Secrets
kubectl get secrets -n bidpivot
```

### 4.4 部署应用

```bash
# 应用所有 K8s 资源
kubectl apply -f k8s/ -n bidpivot

# 或按顺序逐个应用
kubectl apply -f k8s/postgres-deployment.yaml -n bidpivot
kubectl apply -f k8s/redis-deployment.yaml -n bidpivot
kubectl apply -f k8s/qdrant-deployment.yaml -n bidpivot
kubectl apply -f k8s/minio-deployment.yaml -n bidpivot
kubectl apply -f k8s/backend-deployment.yaml -n bidpivot
kubectl apply -f k8s/celery-deployment.yaml -n bidpivot
kubectl apply -f k8s/frontend-deployment.yaml -n bidpivot
kubectl apply -f k8s/ingress.yaml -n bidpivot
```

### 4.5 验证部署

```bash
# 查看所有 Pod 状态
kubectl get pods -n bidpivot

# 查看服务状态
kubectl get svc -n bidpivot

# 查看 Ingress 状态
kubectl get ingress -n bidpivot

# 查看 Pod 日志
kubectl logs -f deployment/bidpivot-backend -n bidpivot
kubectl logs -f deployment/bidpivot-celery -n bidpivot

# 进入 Pod 调试
kubectl exec -it deployment/bidpivot-backend -n bidpivot -- /bin/sh
```

### 4.6 Ingress 配置示例

```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: bidpivot-ingress
  namespace: bidpivot
  annotations:
    nginx.ingress.kubernetes.io/proxy-body-size: "100m"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "120"
    nginx.ingress.kubernetes.io/websocket-services: "bidpivot-backend"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"  # 使用 cert-manager
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - your-domain.com
      secretName: bidpivot-tls
  rules:
    - host: your-domain.com
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: bidpivot-backend
                port:
                  number: 8000
          - path: /ws
            pathType: Prefix
            backend:
              service:
                name: bidpivot-backend
                port:
                  number: 8000
          - path: /
            pathType: Prefix
            backend:
              service:
                name: bidpivot-frontend
                port:
                  number: 80
```

### 4.7 扩缩容

```bash
# 手动扩缩后端 Pod
kubectl scale deployment bidpivot-backend --replicas=3 -n bidpivot

# 手动扩缩 Celery Worker Pod
kubectl scale deployment bidpivot-celery --replicas=2 -n bidpivot

# 配置 HPA 自动扩缩（需安装 Metrics Server）
kubectl autoscale deployment bidpivot-backend \
  --min=2 --max=5 --cpu-percent=70 -n bidpivot
```

### 4.8 滚动更新

```bash
# 更新镜像版本
kubectl set image deployment/bidpivot-backend \
  backend=your-registry/bidpivot-backend:v2.0.0 -n bidpivot

# 查看滚动更新状态
kubectl rollout status deployment/bidpivot-backend -n bidpivot

# 回滚到上一版本
kubectl rollout undo deployment/bidpivot-backend -n bidpivot
```

---

## 5. 环境变量说明

### 5.1 应用核心配置

| 变量名 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| `APP_NAME` | 应用名称 | `BidPivot` | 否 |
| `APP_ENV` | 运行环境 | `development` | 否 |
| `DEBUG` | 调试模式 | `true` | 否 |
| `SECRET_KEY` | 应用密钥（加密用） | 无 | **是** |
| `JWT_SECRET_KEY` | JWT 签名密钥 | 无 | **是** |
| `JWT_ALGORITHM` | JWT 算法 | `HS256` | 否 |
| `JWT_EXPIRE_MINUTES` | Token 过期时间（分钟） | `1440`（24小时） | 否 |
| `CORS_ORIGINS` | 允许的跨域来源 | `["http://localhost:3000"]` | 否 |
| `LOG_LEVEL` | 日志级别 | `INFO` | 否 |
| `WORKERS` | Uvicorn Worker 数量 | `4` | 否 |

### 5.2 数据库配置

| 变量名 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| `DATABASE_URL` | 数据库连接字符串 | `postgresql+asyncpg://bidpivot:bidpivot@localhost:5432/bidpivot` | 否 |
| `POSTGRES_HOST` | PostgreSQL 主机 | `localhost` | 否 |
| `POSTGRES_PORT` | PostgreSQL 端口 | `5432` | 否 |
| `POSTGRES_USER` | 数据库用户名 | `bidpivot` | 否 |
| `POSTGRES_PASSWORD` | 数据库密码 | 无 | **是** |
| `POSTGRES_DB` | 数据库名称 | `bidpivot` | 否 |
| `DB_POOL_SIZE` | 连接池大小 | `20` | 否 |
| `DB_MAX_OVERFLOW` | 连接池溢出上限 | `10` | 否 |

### 5.3 Redis 配置

| 变量名 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| `REDIS_URL` | Redis 连接字符串 | `redis://localhost:6379/0` | 否 |
| `REDIS_PASSWORD` | Redis 密码 | 空 | 否 |
| `CELERY_BROKER_URL` | Celery Broker URL | 同 `REDIS_URL` | 否 |
| `CELERY_RESULT_BACKEND` | Celery 结果存储 URL | 同 `REDIS_URL` | 否 |

### 5.4 向量数据库配置

| 变量名 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| `QDRANT_URL` | Qdrant 连接地址 | `http://localhost:6333` | 否 |
| `QDRANT_API_KEY` | Qdrant API Key | 空 | 否 |
| `QDRANT_COLLECTION_PREFIX` | 集合名前缀 | `bidpivot` | 否 |
| `EMBEDDING_MODEL` | 向量嵌入模型 | `text-embedding-3-small` | 否 |
| `EMBEDDING_DIM` | 向量维度 | `1536` | 否 |

### 5.5 LLM 配置

| 变量名 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| `LLM_PROVIDER` | LLM 提供商 | `openai` | 否 |
| `LLM_API_KEY` | LLM API Key | 无 | **是** |
| `LLM_BASE_URL` | LLM API 地址（自定义/本地） | 空 | 否 |
| `LLM_MODEL_NAME` | 模型名称 | `gpt-4o` | 否 |
| `LLM_TEMPERATURE` | 生成温度 | `0.7` | 否 |
| `LLM_TOP_P` | Top P 采样 | `0.9` | 否 |
| `LLM_MAX_TOKENS` | 最大输出 Token 数 | `4096` | 否 |
| `LLM_TIMEOUT` | API 调用超时（秒） | `120` | 否 |

### 5.6 文件存储配置

| 变量名 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| `MINIO_ENDPOINT` | MinIO 端点 | `localhost:9000` | 否 |
| `MINIO_ACCESS_KEY` | MinIO Access Key | `minioadmin` | 否 |
| `MINIO_SECRET_KEY` | MinIO Secret Key | 无 | **是** |
| `MINIO_BUCKET_NAME` | 默认存储桶 | `bidpivot` | 否 |
| `MINIO_USE_SSL` | 是否使用 SSL | `false` | 否 |
| `UPLOAD_MAX_SIZE_MB` | 最大上传文件大小（MB） | `100` | 否 |

### 5.7 Celery 配置

| 变量名 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| `CELERY_CONCURRENCY` | Worker 并发数 | `4` | 否 |
| `CELERY_MAX_TASKS_PER_CHILD` | 单 Worker 最大任务数 | `100` | 否 |
| `CELERY_TASK_TIMEOUT` | 单任务超时（秒） | `600` | 否 |
| `CELERY_QUEUES` | 监听队列 | `default,generation` | 否 |

---

## 6. 数据库迁移

BidPivot 使用 Alembic 管理数据库迁移。

### 6.1 常用命令

```bash
cd backend

# 查看当前迁移版本
alembic current

# 查看迁移历史
alembic history --verbose

# 执行所有待执行的迁移（升级到最新）
alembic upgrade head

# 回退一个版本
alembic downgrade -1

# 回退到指定版本
alembic downgrade <revision_id>

# 回退到最初状态（危险！）
alembic downgrade base

# 生成新的迁移文件（自动检测模型变更）
alembic revision --autogenerate -m "描述变更内容"

# 查看 SQL 而不执行（干运行）
alembic upgrade head --sql
```

### 6.2 Docker 环境中执行迁移

```bash
# 在运行中的 backend 容器内执行迁移
docker-compose exec backend alembic upgrade head

# 或使用一次性容器执行
docker-compose run --rm backend alembic upgrade head
```

### 6.3 迁移注意事项

1. **生产环境迁移前务必备份数据库**：
   ```bash
   pg_dump -U bidpivot -d bidpivot > backup_$(date +%Y%m%d_%H%M%S).sql
   ```

2. **检查自动生成的迁移文件**：`--autogenerate` 可能遗漏某些变更（如表重命名），需人工审查。

3. **大数据量迁移**：对于大表的 ALTER 操作，考虑分批执行或使用在线 DDL 工具（如 `pg_repack`）。

4. **多环境同步**：确保开发、测试、生产环境的迁移版本一致。

---

## 7. SSL 证书配置

### 7.1 Let's Encrypt（推荐用于生产环境）

使用 Certbot 自动申请和续期证书：

```bash
# 安装 Certbot
sudo apt install -y certbot python3-certbot-nginx

# 申请证书（Nginx 插件模式，自动修改 Nginx 配置）
sudo certbot --nginx -d your-domain.com

# 或仅申请证书（手动配置 Nginx）
sudo certbot certonly --webroot -w /opt/BidPivot/frontend/dist -d your-domain.com

# 测试自动续期
sudo certbot renew --dry-run

# 设置自动续期（通常 Certbot 安装时已自动配置）
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

申请成功后，更新 Nginx 配置：

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # HSTS
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # ... 其余配置同上 ...
}

# HTTP 重定向到 HTTPS
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$host$request_uri;
}
```

### 7.2 自签名证书（开发/测试环境）

```bash
# 生成自签名证书（有效期 365 天）
openssl req -x509 -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout /etc/ssl/private/bidpivot-selfsigned.key \
  -out /etc/ssl/certs/bidpivot-selfsigned.crt \
  -subj "/C=CN/ST=Beijing/L=Beijing/O=BidPivot/CN=localhost"

# 生成 Diffie-Hellman 参数（增强安全性）
openssl dhparam -out /etc/ssl/certs/dhparam.pem 2048
```

Nginx 配置中替换证书路径：

```nginx
ssl_certificate /etc/ssl/certs/bidpivot-selfsigned.crt;
ssl_certificate_key /etc/ssl/private/bidpivot-selfsigned.key;
ssl_dhparam /etc/ssl/certs/dhparam.pem;
```

### 7.3 Kubernetes 环境 SSL

使用 cert-manager 自动管理证书：

```bash
# 安装 cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.14.0/cert-manager.yaml

# 创建 ClusterIssuer
cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@your-domain.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
      - http01:
          ingress:
            class: nginx
EOF
```

在 Ingress 中添加注解即可自动申请证书（参见 [4.6 Ingress 配置示例](#46-ingress-配置示例)）。

---

## 8. 常见问题

### 8.1 连接类问题

**Q: 后端无法连接 PostgreSQL**

```
sqlalchemy.exc.OperationalError: connection to server at "localhost" failed
```

排查步骤：
1. 确认 PostgreSQL 已启动：`sudo systemctl status postgresql`
2. 检查监听地址：`sudo ss -tlnp | grep 5432`
3. 检查 `pg_hba.conf` 是否允许对应 IP/用户的连接
4. 检查防火墙：`sudo ufw allow 5432`
5. Docker 环境中确认使用服务名 `postgres` 而非 `localhost`

**Q: 后端无法连接 Redis**

```
redis.exceptions.ConnectionError: Error connecting to redis:6379
```

排查步骤：
1. 确认 Redis 已启动：`redis-cli ping`
2. 检查 Redis 是否设置了密码：对比 `REDIS_URL` 中的密码
3. Docker 环境中确认 Redis 容器健康：`docker-compose ps redis`

**Q: Celery Worker 无法连接 Broker**

```
celery.exceptions.ImproperlyConfigured: Missing broker transport
```

排查步骤：
1. 确认 `CELERY_BROKER_URL` 配置正确
2. 确认 Redis 可访问且密码正确
3. 检查 Redis 是否达到了最大连接数限制

**Q: WebSocket 连接失败**

排查步骤：
1. 确认 Nginx 已正确配置 WebSocket 代理（`Upgrade` 和 `Connection` 头）
2. 检查后端 WebSocket 端点是否正常
3. 确认防火墙/安全组允许 WebSocket 连接

### 8.2 数据库迁移问题

**Q: `alembic upgrade head` 报错 "relation already exists"**

```
sqlalchemy.exc.ProgrammingError: relation "xxx" already exists
```

解决方案：
```bash
# 标记当前版本为已迁移（跳过冲突的迁移）
alembic stamp head
```

**Q: 迁移文件冲突（多分支合并后）**

解决方案：
```bash
# 创建合并迁移
alembic merge -m "merge multiple heads" <rev1> <rev2>
```

**Q: 自动生成的迁移遗漏了某些变更**

原因：Alembic 的 `--autogenerate` 无法检测到所有变更（如表重命名、列类型变更需手动审查）。

解决方案：生成后仔细检查迁移文件，手动补充遗漏的操作。

### 8.3 权限与文件问题

**Q: MinIO 上传文件失败 "Access Denied"**

排查步骤：
1. 确认 `MINIO_ACCESS_KEY` 和 `MINIO_SECRET_KEY` 正确
2. 确认存储桶已创建：访问 MinIO Console（端口 9001）
3. 检查存储桶策略是否允许读写

**Q: Nginx 返回 403 Forbidden**

排查步骤：
1. 检查前端 `dist` 目录权限：`ls -la /opt/BidPivot/frontend/dist/`
2. 确保 Nginx 用户有权读取文件：`chmod -R 755 /opt/BidPivot/frontend/dist/`
3. 检查 SELinux 状态（CentOS/RHEL）：`getenforce`，必要时 `setsebool -P httpd_can_network_connect 1`

**Q: 文件上传大小超过限制**

1. 检查 Nginx 配置：`client_max_body_size`（默认 1MB，BidPivot 需设为 100M）
2. 检查后端配置：`UPLOAD_MAX_SIZE_MB` 环境变量
3. 检查 Ingress 配置：`nginx.ingress.kubernetes.io/proxy-body-size`

### 8.4 性能问题

**Q: 标书生成任务超时**

排查步骤：
1. 检查 Celery Worker 日志：`docker-compose logs -f celery-worker`
2. 确认 LLM API 可达且响应正常
3. 调整 `CELERY_TASK_TIMEOUT`（默认 600 秒）
4. 检查 `LLM_TIMEOUT` 设置
5. 检查 Qdrant 向量检索性能

**Q: 数据库连接池耗尽**

```
sqlalchemy.exc.TimeoutError: QueuePool limit of size X overflow Y reached
```

解决方案：
1. 增大连接池：调整 `DB_POOL_SIZE` 和 `DB_MAX_OVERFLOW`
2. 检查是否存在连接泄漏（长时间未释放的事务）
3. 考虑使用 PgBouncer 做连接池代理

### 8.5 容器相关问题

**Q: Docker 容器反复重启**

```bash
# 查看容器日志
docker-compose logs --tail=100 <service_name>

# 查看容器退出码
docker inspect <container_name> --format='{{.State.ExitCode}}'
```

常见原因：
- 依赖服务未就绪（数据库、Redis 未启动）→ 增加 `depends_on` 和 `healthcheck`
- 环境变量缺失 → 检查 `.env` 文件
- 端口冲突 → `sudo ss -tlnp | grep <port>`

**Q: Docker Compose 启动顺序问题**

确保 `docker-compose.yml` 中正确定义了 `depends_on` 和健康检查：

```yaml
services:
  backend:
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      qdrant:
        condition: service_healthy

  postgres:
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U bidpivot"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
```

---

## 附录：快速命令参考

```bash
# ===== Docker Compose =====
docker-compose up -d                    # 启动所有服务
docker-compose down                     # 停止所有服务
docker-compose ps                       # 查看服务状态
docker-compose logs -f                  # 查看实时日志
docker-compose exec backend bash        # 进入后端容器
docker-compose exec backend alembic upgrade head  # 执行数据库迁移

# ===== 后端 =====
uvicorn app.main:app --reload           # 开发模式启动
pytest                                  # 运行测试
alembic upgrade head                    # 执行迁移
alembic revision --autogenerate -m "msg"  # 生成迁移文件

# ===== 前端 =====
npm run dev                             # 开发模式启动
npm run build                           # 生产构建
npm run lint                            # 代码检查

# ===== Celery =====
celery -A app.celery worker --loglevel=info  # 启动 Worker
celery -A app.celery flower --port=5555      # 启动监控面板

# ===== Kubernetes =====
kubectl apply -f k8s/ -n bidpivot       # 部署
kubectl get pods -n bidpivot            # 查看 Pod
kubectl logs -f <pod-name> -n bidpivot  # 查看日志
kubectl rollout restart deployment/<name> -n bidpivot  # 重启部署
```
