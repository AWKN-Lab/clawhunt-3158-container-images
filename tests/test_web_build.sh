#!/usr/bin/env bash
# 前端构建本地实测（#3158）：不依赖 docker，只验证 Dockerfile 构建阶段
# 做的事（npm ci + npm run build）与 nginx.conf 的关键指令。
# nginx -t 本机无 nginx 二进制，无法执行，见 ACCEPTANCE.md。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/web"

echo "--- npm ci ---"
npm ci --omit=dev --no-audit --no-fund

echo "--- npm run build ---"
npm run build

echo "--- dist 内容 ---"
ls -la dist/
test -f dist/index.html || { echo "FAIL: dist/index.html missing"; exit 1; }
grep -q "会员空间平台" dist/index.html || { echo "FAIL: dist/index.html 内容不对"; exit 1; }
echo "dist/index.html ok"

echo "--- nginx.conf 关键指令 ---"
grep -q "gzip on;" nginx.conf
grep -q "try_files \$uri \$uri/ /index.html;" nginx.conf
grep -q "location = /healthz" nginx.conf
grep -q "listen       8080;" nginx.conf
echo "nginx.conf ok"

rm -rf dist node_modules
echo "WEB-BUILD PASS"
