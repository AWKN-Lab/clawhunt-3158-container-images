#!/usr/bin/env bash
# Trivy 本地实测（#3158）：本机无 docker，扫不了构建出的镜像；
# 此脚本做三件能做的事，证明工作流里 Trivy 步骤的配置本身有效：
#   1. 真实依赖（app/requirements.txt）扫 CRITICAL/HIGH：须干净（exit 0）。
#   2. 含 CRITICAL 漏洞的样本（tests/fixtures/vuln-app/，pillow 9.5.0）：
#      用工作流同款参数（severity CRITICAL、exit-code 1）扫，须失败（exit 1），
#      证明“有 CRITICAL 就失败”这条机制本身是通的。
#   3. 两份 Dockerfile 的配置扫描（trivy config）：须 0  findings。
# 镜像扫描（验收 4 的完整形态）仍待有 docker 的环境执行，见 ACCEPTANCE.md。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TRIVY="${TRIVY:-$(command -v trivy || true)}"

if [ -z "$TRIVY" ]; then
    echo "SKIP: trivy binary not found (set TRIVY=... to run this check)"
    echo "TRIVY-LOCAL SKIP"
    exit 0
fi

echo "trivy: $TRIVY"
"$TRIVY" --version

echo "--- 1. 真实依赖扫描（expect exit 0） ---"
"$TRIVY" fs --scanners vuln --severity CRITICAL,HIGH --exit-code 1 \
    "$ROOT/app/requirements.txt"
echo "real requirements: clean"

echo "--- 2. CRITICAL 样本扫描（expect exit 1） ---"
set +e
"$TRIVY" fs --scanners vuln --severity CRITICAL --exit-code 1 \
    "$ROOT/tests/fixtures/vuln-app/" 2>&1 | tail -8
rc=${PIPESTATUS[0]}
set -e
if [ "$rc" -ne 1 ]; then
    echo "FAIL: 样本扫描应以 exit 1 失败，实测 exit $rc"
    exit 1
fi
echo "vuln fixture correctly fails with exit 1"

echo "--- 3. Dockerfile 配置扫描（expect exit 0） ---"
# 注意：trivy config 一次只接受一个 target；逐份扫两份交付 Dockerfile。
# 漏洞样本 Dockerfile.vuln-base 不在此列（它故意没写 USER，见第 4 步）。
for df in "$ROOT/app/Dockerfile" "$ROOT/web/Dockerfile"; do
    "$TRIVY" config --severity CRITICAL,HIGH --exit-code 1 "$df"
done
echo "dockerfile config: clean"

echo "--- 4. 旧基础镜像样本配置扫描（只记录，不作断言） ---"
"$TRIVY" config --severity CRITICAL,HIGH --exit-code 0 \
    "$ROOT/tests/fixtures/Dockerfile.vuln-base" 2>&1 | tail -6 || true
echo "(旧基础镜像的漏洞只能由镜像扫描发现，配置扫描扫不出来；见 ACCEPTANCE.md)"

echo "TRIVY-LOCAL PASS"
