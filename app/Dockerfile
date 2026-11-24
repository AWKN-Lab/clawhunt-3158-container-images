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

# 装完运行时依赖后**升级 setuptools 与 wheel**：
# python:3.11-slim 自带 setuptools 79.0.1 / wheel 0.45.1，
#   - setuptools 的 METADATA 依赖 jaraco.context 5.3.0（CVE-2026-23949 路径遍历，修复 6.1.0）
#   - 系统 dist-packages 里的 wheel 0.45.1（CVE-2026-24049 提权，修复 0.46.2）
# Trivy 扫的是 **METADATA 文件** ⇒ 实装版本升级了不够，**旧文件必须删**，
# 否则镜像里仍留着可被判 HIGH 的 METADATA（门禁：CRITICAL/HIGH 即失败）。
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt \
    && pip install --no-cache-dir --prefix=/install --upgrade "setuptools>=80.9.0" "wheel>=0.46.2"

# ---------- runtime：非 root 运行，只含运行所需文件 ----------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd -r app -g 10001 \
    && useradd -r -u 10001 -g app app \
    && mkdir -p /app \
    && chown app:app /app \
    # 删掉基础镜像自带的旧 setuptools / wheel（它们的 METADATA 带已知 HIGH 漏洞），
    # 运行时只用 /usr/local 下 builder 装的新版（setuptools>=80.9.0 / wheel>=0.46.2）。
    && rm -rf /usr/lib/python3/dist-packages/setuptools* /usr/lib/python3/dist-packages/wheel* \
    && python3 -c "import setuptools, wheel; print('setuptools', setuptools.__version__, '| wheel', wheel.__version__)"

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
