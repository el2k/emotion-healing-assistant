@echo off
REM 一键启动：后端 FastAPI + 前端 Vite 开发服务
cd /d %~dp0

echo [1/2] 启动后端 http://127.0.0.1:8000
start "healing-backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\python.exe run.py"

echo [2/2] 启动前端 http://localhost:5173
start "healing-frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo 已启动！聊天入口：http://localhost:5173  管理员登录后可访问 /admin
pause