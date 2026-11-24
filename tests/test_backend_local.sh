#!/usr/bin/env bash
# 后端桩本地实测（#3158）：不依赖 docker，只验证 Dockerfile 的 CMD
# （uvicorn main:app --host 0.0.0.0 --port 8000 --no-access-log）
# 在本机能跑通、/healthz 返回 200。
# 容器内 whoami 输出 app（验收 1）本机无 docker 无法执行，见 ACCEPTANCE.md。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="${CH3158_VENV:-/tmp/ch3158-venv}"
PORT="${CH3158_PORT:-8000}"

if [ ! -x "$VENV/bin/uvicorn" ]; then
    echo "creating venv at $VENV"
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -q -r "$ROOT/app/requirements.txt"
fi

cd "$ROOT/app"
"$VENV/bin/python" -m uvicorn main:app --host 127.0.0.1 --port "$PORT" --no-access-log &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT

ok=""
for _ in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:$PORT/healthz" >/dev/null 2>&1; then ok=1; break; fi
    sleep 0.5
done
[ -n "$ok" ] || { echo "FAIL: server did not come up on $PORT"; exit 1; }

echo "--- GET /healthz ---"
curl -fsS "http://127.0.0.1:$PORT/healthz"
echo
echo "--- GET / ---"
curl -fsS "http://127.0.0.1:$PORT/"
echo

# /healthz 必须是 {"status": "ok"}
body="$(curl -fsS "http://127.0.0.1:$PORT/healthz")"
case "$body" in
    *'"status": "ok"'*|*'"status":"ok"'*) echo "healthz ok: $body" ;;
    *) echo "FAIL: unexpected /healthz body: $body"; exit 1 ;;
esac

echo "BACKEND-LOCAL PASS"
