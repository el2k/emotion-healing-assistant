@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 情绪陪伴 · 命令行聊天

echo ============================================
echo    情绪陪伴 · 命令行聊天（Docker 容器）
echo ============================================
echo.

:: 1) 检查 Docker Desktop 是否已启动
docker info >nul 2>&1
if errorlevel 1 (
    echo [错误] Docker Desktop 还没启动。
    echo        请先双击桌面上的 Docker Desktop 图标，等它启动完成后再运行本脚本。
    echo.
    pause
    exit /b 1
)

:: 2) 检查容器是否在运行（healthy）
docker compose ps --format "{{.Status}}" 2>nul | findstr /i "healthy" >nul
if errorlevel 1 (
    echo [提示] 容器未运行或未就绪，正在启动容器...
    docker compose up -d
    echo 等待服务就绪（约 10 秒）...
    timeout /t 10 >nul
)

:: 3) 列出角色
echo 【可用角色】
docker compose exec -T app python cli_chat.py --list --no-color
echo.

:: 4) 选择角色
set "PERSONA="
set /p PERSONA=请输入角色名或 id（直接回车 = 小窝 nuan）：

if "%PERSONA%"=="" set PERSONA=nuan

echo.
echo 进入聊天（输入消息回车发送；/list 看角色、/persona 换角色、/exit 退出）
echo --------------------------------------------
docker compose exec app python cli_chat.py -p %PERSONA%

echo.
echo 聊天已结束。
pause