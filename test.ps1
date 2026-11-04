# BidPivot 测试环境启动脚本 (Windows)

Write-Host '=== BidPivot 测试环境启动 ===' -ForegroundColor Cyan

# 检查依赖
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host '错误: 未安装 Python' -ForegroundColor Red; exit 1
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host '错误: 未安装 Node.js' -ForegroundColor Red; exit 1
}

# 检查 config.json
if (-not (Test-Path 'backend\config.json')) {
    Write-Host '提示: 未找到 backend\config.json，使用默认配置' -ForegroundColor Yellow
    Write-Host '如需自定义配置，复制 backend\config.json.example 为 backend\config.json 并修改' -ForegroundColor Yellow
} else {
    Write-Host '已加载 backend\config.json' -ForegroundColor Green
}

# 创建日志目录
New-Item -ItemType Directory -Force -Path logs | Out-Null

# 创建虚拟环境
if (-not (Test-Path 'backend\venv')) {
    Write-Host '创建 Python 虚拟环境...'
    python -m venv backend\venv
}

# 激活虚拟环境
& backend\venv\Scripts\Activate.ps1

# 安装后端依赖
Write-Host '安装后端依赖...'
pip install -r backend\requirements.txt -q

# 安装前端依赖
Write-Host '安装前端依赖...'
Set-Location frontend; npm install --silent; Set-Location ..

# 启动 Docker 基础服务
if (Get-Command docker -ErrorAction SilentlyContinue) {
    Write-Host '启动 Docker 基础服务...'
    docker-compose up -d postgres redis qdrant minio
    Write-Host '等待数据库就绪...'
    Start-Sleep -Seconds 5
}

# 运行数据库迁移
Write-Host '运行数据库迁移...'
Set-Location backend; alembic upgrade head 2>$null; Set-Location ..

# 启动后端
Write-Host '启动后端服务...'
Start-Process -FilePath 'backend\venv\Scripts\python.exe' -ArgumentList '-m', 'uvicorn', 'app.main:app', '--reload', '--host', '0.0.0.0', '--port', '8000' -RedirectStandardOutput 'logs\backend.log' -RedirectStandardError 'logs\backend-error.log' -WindowStyle Hidden

# 启动 Celery Worker
Write-Host '启动 Celery Worker...'
Start-Process -FilePath 'backend\venv\Scripts\celery.exe' -ArgumentList '-A', 'app.celery_app', 'worker', '--loglevel=info' -RedirectStandardOutput 'logs\celery.log' -RedirectStandardError 'logs\celery-error.log' -WindowStyle Hidden

# 启动前端
Write-Host '启动前端开发服务器...'
Start-Process -FilePath 'npm.cmd' -ArgumentList 'run', 'dev' -WorkingDirectory 'frontend' -RedirectStandardOutput 'logs\frontend.log' -RedirectStandardError 'logs\frontend-error.log' -WindowStyle Hidden

Write-Host ''
Write-Host '=== 服务启动完成 ===' -ForegroundColor Green
Write-Host '前端: http://localhost:5173'
Write-Host '后端: http://localhost:8000'
Write-Host 'API 文档: http://localhost:8000/docs'
Write-Host ''
Write-Host '日志文件: logs\backend.log, logs\celery.log, logs\frontend.log'
