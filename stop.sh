#!/bin/bash
# BidPivot 停止服务脚本

echo "=== 停止 BidPivot 服务 ==="

for pidfile in logs/backend.pid logs/celery.pid logs/frontend.pid; do
    if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid"
            echo "已停止进程 $pid"
        fi
        rm -f "$pidfile"
    fi
done

if command -v docker >/dev/null 2>&1; then
    # 检查是否有docker权限，如果没有则使用sudo
    if docker info >/dev/null 2>&1; then
        docker-compose down
    else
        echo "需要sudo权限停止Docker..."
        sudo docker-compose down
    fi
    echo "已停止 Docker 服务"
fi

echo "=== 所有服务已停止 ==="
