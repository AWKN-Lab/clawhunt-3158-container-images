"""会员空间平台后端 · 最小可运行桩（#3158）。

只为让后端 Dockerfile 有东西可装、可探活：提供 /healthz（供
HEALTHCHECK 调用）与根路径占位。真实业务后端替换本文件即可，
Dockerfile、端口、探活路径、启动命令均不需改。

与 #3190 的关系：生产日志应接 app/core/logging.py 的结构化日志
中间件（单行 JSON 到 stdout、落盘前脱敏）；本桩只打一条启动日志，
不记录请求体。
"""

import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend-stub")

app = FastAPI(title="membership-backend-stub")


@app.get("/healthz")
def healthz() -> JSONResponse:
    """存活探活：Dockerfile HEALTHCHECK 与编排层调用此接口。"""
    return JSONResponse({"status": "ok"})


@app.get("/")
def index() -> JSONResponse:
    return JSONResponse(
        {"service": "membership-backend", "status": "stub", "health": "/healthz"}
    )


if __name__ == "__main__":  # 本地调试用，容器内走 uvicorn 命令
    import uvicorn

    logger.info("starting backend stub on 8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
