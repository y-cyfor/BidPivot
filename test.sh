#!/bin/bash
# BidPivot 测试环境启动脚本（前台运行模式）

# 切换到脚本所在目录
cd "$(dirname "$0")"

echo "=== BidPivot 测试环境启动 ==="

# 检查依赖
command -v python3 >/dev/null 2>&1 || { echo "错误: 未安装 Python3"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "错误: 未安装 Node.js"; exit 1; }

# 检查端口是否被占用，若占用则自动杀死占用进程
check_port() {
    local pid=$(sudo lsof -Pi :$1 -sTCP:LISTEN -t 2>/dev/null)
    if [ -n "$pid" ]; then
        echo "端口 $1 已被进程 $pid 占用，正在释放..."
        sudo kill -9 $pid 2>/dev/null
        sleep 1
        # 再次检查是否释放成功
        if sudo lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null 2>&1; then
            echo "错误: 端口 $1 释放失败，请手动处理"
            exit 1
        fi
        echo "端口 $1 已释放"
    fi
}
check_port 8000
check_port 5173

# 检查 config.json
if [ ! -f "backend/config.json" ]; then
    echo "提示: 未找到 backend/config.json，使用默认配置"
    echo "如需自定义配置，复制 backend/config.json.example 为 backend/config.json 并修改"
else
    echo "已加载 backend/config.json"
fi

# 创建日志目录
mkdir -p logs

# 创建虚拟环境（如果不存在或是Windows风格则重新创建）
if [ ! -d "backend/venv" ] || [ ! -f "backend/venv/bin/activate" ]; then
    echo "创建 Python 虚拟环境..."
    rm -rf backend/venv
    python3 -m venv backend/venv
fi

# 激活虚拟环境
source backend/venv/bin/activate

# 安装后端依赖
echo "安装后端依赖..."
pip install -r backend/requirements.txt -q

# 安装前端依赖（Vben Admin使用pnpm）
echo "安装前端依赖..."
cd vben-admin && pnpm install --silent && cd ..

# 修复前端依赖的执行权限
if [ -f "frontend/node_modules/.bin/vite" ]; then
    chmod +x frontend/node_modules/.bin/*
fi

# 启动 Docker 基础服务
if command -v docker >/dev/null 2>&1; then
    echo "启动 Docker 基础服务..."
    # 检查是否有docker权限，如果没有则使用sudo
    if docker info >/dev/null 2>&1; then
        docker-compose up -d postgres redis qdrant minio
    else
        echo "需要sudo权限运行Docker..."
        sudo docker-compose up -d postgres redis qdrant minio
    fi
    echo "等待数据库就绪..."
    for i in {1..30}; do
        if docker-compose exec -T postgres pg_isready -U postgres >/dev/null 2>&1; then
            echo "数据库已就绪"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "警告: 数据库启动超时，继续执行..."
        fi
        sleep 1
    done
fi

# 运行数据库迁移
echo "运行数据库迁移..."
cd backend && alembic upgrade head 2>/dev/null || echo "跳过迁移（首次运行或 Alembic 未配置）" && cd ..

# 定义清理函数
cleanup() {
    echo ""
    echo "=== 正在停止服务 ==="

    # 停止后端
    if [ -f "logs/backend.pid" ]; then
        kill $(cat logs/backend.pid) 2>/dev/null || true
        rm -f logs/backend.pid
    fi

    # 停止 Celery
    if [ -f "logs/celery.pid" ]; then
        kill $(cat logs/celery.pid) 2>/dev/null || true
        rm -f logs/celery.pid
    fi

    # 停止前端
    if [ -f "logs/frontend.pid" ]; then
        kill $(cat logs/frontend.pid) 2>/dev/null || true
        rm -f logs/frontend.pid
    fi

    # 停止 Docker 服务
    if command -v docker >/dev/null 2>&1; then
        if docker info >/dev/null 2>&1; then
            docker-compose down
        else
            sudo docker-compose down
        fi
    fi

    echo "=== 所有服务已停止 ==="
    exit 0
}

# 捕获 Ctrl+C 信号
trap cleanup SIGINT SIGTERM

# 启动后端
echo "启动后端服务..."
cd backend
BIDPIVOT_SEED_ADMIN=true nohup python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > ../logs/backend.pid
cd ..

# 启动 Celery Worker
echo "启动 Celery Worker..."
cd backend
nohup celery -A app.celery_app worker --loglevel=info > ../logs/celery.log 2>&1 &
CELERY_PID=$!
echo $CELERY_PID > ../logs/celery.pid
cd ..

# 启动前端（Vben Admin使用pnpm）
echo "启动前端开发服务器..."
cd vben-admin
nohup pnpm --filter @bidpivot/frontend dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > ../logs/frontend.pid
cd ..

echo ""
echo "=== 服务启动完成 ==="
echo "前端: http://localhost:5173"
echo "后端: http://localhost:8000"
echo "API 文档: http://localhost:8000/docs"
echo ""
echo "按 Ctrl+C 停止所有服务"
echo ""

# 持续显示日志（合并所有日志）
tail -f logs/backend.log logs/celery.log logs/frontend.log
