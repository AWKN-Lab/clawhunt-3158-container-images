# syntax=docker/dockerfile:1
# 会员空间平台 · 后端镜像（#3158）
#
# 构建上下文为仓库根目录（见 .github/workflows/image.yml），
# 本文件只取 app/ 下的源码与依赖；.env、.git 等由根目录 .dockerignore 排除。
# 基础镜像已核验（2026-11-24，Docker Hub API）：
#   python:3.11-slim  amd64 digest sha256:b701198cb708…

# ---------- builder：只装依赖，不留源码 ----------
FROM python:3.11-slim AS builder

WORKDIR /build

COPY app/requirements.txt .

RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------- runtime：非 root 运行，只含运行所需文件 ----------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd -r app -g 10001 \
    && useradd -r -u 10001 -g app app \
    && mkdir -p /app \
    && chown app:app /app

WORKDIR /app

COPY --from=builder /install /usr/local
COPY --chown=app:app app/main.py ./main.py

USER app

EXPOSE 8000

# python:3.11-slim 自带 python，不装 curl/wget；用标准库 urllib 探活
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"

# --no-access-log：访问日志由 #3190 的结构化日志中间件统一输出，
# 避免 uvicorn 默认格式的访问日志行重复出现且未经脱敏
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
