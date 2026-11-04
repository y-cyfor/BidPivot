@echo off
chcp 65001 >nul
setlocal

title BidPivot Dev Server

echo ========================================
echo    BidPivot Dev Server
echo ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found
    pause
    exit /b 1
)

where node >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found
    pause
    exit /b 1
)

if not exist logs mkdir logs
type nul > logs\backend.log
type nul > logs\frontend.log
type nul > logs\celery.log

if not exist backend\venv (
    echo [INFO] Creating virtual environment...
    python -m venv backend\venv
)

call backend\venv\Scripts\activate.bat

echo [INFO] Installing backend dependencies...
pip install -r backend\requirements.txt -q

echo [INFO] Installing frontend dependencies...
cd frontend
call npm install --silent
cd ..

where docker >nul 2>&1
if not errorlevel 1 (
    echo [INFO] Starting Docker services...
    docker-compose up -d postgres redis qdrant minio
    echo [INFO] Waiting for database...
    timeout /t 5 /nobreak >nul
)

echo [INFO] Running database migrations...
cd backend
alembic upgrade head 2>nul
cd ..

echo.
echo [INFO] Starting dev servers...
echo.

set "PROJECT_DIR=%~dp0"
set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
set "TMP_DIR=%PROJECT_DIR%\.tmp"
if not exist "%TMP_DIR%" mkdir "%TMP_DIR%"

(
echo @echo off
echo cd /d "%PROJECT_DIR%\backend"
echo call venv\Scripts\activate.bat
echo python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
) > "%TMP_DIR%\start_backend.bat"

(
echo @echo off
echo cd /d "%PROJECT_DIR%\backend"
echo call venv\Scripts\activate.bat
echo celery -A app.celery_app worker --loglevel=info
) > "%TMP_DIR%\start_celery.bat"

(
echo @echo off
echo cd /d "%PROJECT_DIR%\frontend"
echo npm run dev
) > "%TMP_DIR%\start_frontend.bat"

echo [START] Backend server (port 8000)
start "BidPivot Backend" "%TMP_DIR%\start_backend.bat"
timeout /t 2 /nobreak >nul

echo [START] Celery Worker
start "BidPivot Celery" "%TMP_DIR%\start_celery.bat"

echo [START] Frontend dev server (port 5173)
start "BidPivot Frontend" "%TMP_DIR%\start_frontend.bat"

echo.
echo ========================================
echo    All services started!
echo ========================================
echo.
echo    Frontend: http://localhost:5173
echo    Backend:  http://localhost:8000
echo    API Docs: http://localhost:8000/docs
echo.
echo    Close this window to stop all services
echo ========================================
echo.

timeout /t 3 /nobreak >nul

echo [INFO] Monitoring logs...
echo ----------------------------------------
echo.

powershell -Command "Get-Content -Path 'logs\backend.log','logs\frontend.log','logs\celery.log' -Wait -Tail 50"

echo.
echo [INFO] Stopping all services...
taskkill /FI "WINDOWTITLE eq BidPivot*" /F >nul 2>&1
echo [INFO] Done
pause
