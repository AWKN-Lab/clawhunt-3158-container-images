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

# 只装运行时依赖（fastapi + uvicorn）。setuptools / wheel 不装进 /install：
# runtime 不需要它们，装了也会在 COPY 之后被删掉（见下），纯属浪费构建时间。
# 基础镜像自带的 setuptools 79.0.1（_vendor 内嵌旧版 jaraco.context 5.3.0 /
# wheel 0.45.1 的 dist-info，SARIF 实测）也在 COPY 之后删——目录名与新版不同
#（jaraco.context- vs jaraco_context-），COPY 合并时旧文件不会被覆盖。
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
# 运行时**不需要** setuptools / wheel（只装 fastapi + uvicorn，都是 wheel 包）⇒ 整个移出镜像。
# 删除放在 COPY 之后：一次覆盖最终镜像里的全部来源——基础镜像自带的
# setuptools 79.0.1（_vendor 内嵌旧版 jaraco.context 5.3.0 / wheel 0.45.1
# 的 dist-info，SARIF 实测）与顶层 wheel。目录名与新版不同
#（jaraco.context- vs jaraco_context-），COPY 合并时旧文件不会被覆盖，
# 留着就会被 Trivy 判 HIGH。
RUN rm -rf /usr/local/lib/python3.11/site-packages/setuptools \
             /usr/local/lib/python3.11/site-packages/setuptools-*.dist-info \
             /usr/local/lib/python3.11/site-packages/wheel \
             /usr/local/lib/python3.11/site-packages/wheel-*.dist-info \
             /usr/local/lib/python3.11/site-packages/pkg_resources \
             /usr/lib/python3/dist-packages/setuptools* \
             /usr/lib/python3/dist-packages/wheel* \
    && python3 -c "import fastapi, uvicorn; print('runtime deps ok | fastapi', fastapi.__version__)" \
    && python3 -c "import importlib.util as u; assert u.find_spec('setuptools') is None and u.find_spec('wheel') is None; print('setuptools/wheel NOT in runtime image')"

COPY --chown=app:app app/main.py ./main.py

USER app

EXPOSE 8000

# python:3.11-slim 自带 python，不装 curl/wget；用标准库 urllib 探活
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"

# --no-access-log：访问日志由 #3190 的结构化日志中间件统一输出，
# 避免 uvicorn 默认格式的访问日志行重复出现且未经脱敏
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
