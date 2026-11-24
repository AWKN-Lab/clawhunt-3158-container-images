#!/usr/bin/env bash
# #3158 本地验收总跑：pytest 静态核验 + 后端本地实测 + 前端构建实测 + Trivy 本地实测。
# 本机无 docker：镜像构建、容器内验证、镜像扫描、推送均不在本脚本内，
# 见 README.md 与 ACCEPTANCE.md 的未执行清单。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p evidence

VENV="${CH3158_VENV:-/tmp/ch3158-venv}"
if [ ! -x "$VENV/bin/pytest" ]; then
    echo "creating venv at $VENV"
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -q pytest pyyaml fastapi "uvicorn[standard]"
fi
"$VENV/bin/pip" install -q -r "$ROOT/app/requirements.txt"

# Trivy：优先用本机 tools 目录的二进制，其次用 PATH 里的
if [ -z "${TRIVY:-}" ]; then
    if [ -x "$ROOT/../../tools/trivy" ]; then
        export TRIVY="$ROOT/../../tools/trivy"
    elif command -v trivy >/dev/null 2>&1; then
        export TRIVY="$(command -v trivy)"
    fi
fi

echo "=== pytest：Dockerfile / .dockerignore / image.yml 静态核验 ==="
"$VENV/bin/python" -m pytest tests/test_dockerfiles.py tests/test_image_workflow.py -v \
    2>&1 | tee evidence/test-pytest.log
test "${PIPESTATUS[0]}" -eq 0

echo "=== 后端本地实测 ==="
bash tests/test_backend_local.sh 2>&1 | tee evidence/test-backend-local.log
test "${PIPESTATUS[0]}" -eq 0

echo "=== 前端构建实测 ==="
bash tests/test_web_build.sh 2>&1 | tee evidence/test-web-build.log
test "${PIPESTATUS[0]}" -eq 0

echo "=== Trivy 本地实测 ==="
bash tests/test_trivy_local.sh 2>&1 | tee evidence/test-trivy-local.log
test "${PIPESTATUS[0]}" -eq 0

echo
echo "ALL PASS"
