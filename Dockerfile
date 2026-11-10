# syntax=docker/dockerfile:1

# ============================================================
# 阶段一：构建前端（Vue 3 + Vite）产物
# ============================================================
FROM node:20-alpine AS frontend-builder
WORKDIR /build

# 先拷依赖清单，利用层缓存（依赖不变时跳过重装）
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build


# ============================================================
# 阶段二：运行时（Python + FastAPI，同时托管前端 dist）
# ============================================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    DEBUG=false

WORKDIR /app

# 依赖单独一层，源码改动不会触发重装
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# 后端源码（含 uploads/personas 立绘兜底）
COPY backend/ ./backend/

# 前端构建产物：main.py 期望位于 backend/../frontend/dist
COPY --from=frontend-builder /build/dist ./frontend/dist

# 运行期目录（compose 中会挂载宿主机目录覆盖）
RUN mkdir -p /app/backend/data /app/backend/uploads

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)" || exit 1

# 从 backend 目录启动，保证 `app` 包可被导入；reload 由 DEBUG 控制（默认关闭）
WORKDIR /app/backend
CMD ["python", "run.py"]
