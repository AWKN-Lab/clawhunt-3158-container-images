# syntax=docker/dockerfile:1
# 会员空间平台 · 工作台前端镜像（#3158）
#
# 构建上下文为仓库根目录（见 .github/workflows/image.yml）。
# 基础镜像已核验（2026-11-24，Docker Hub API）：
#   node:22-alpine    amd64 digest sha256:12f54cafa58d…
#   nginx:1.30-alpine manifest digest sha256:8eb2b5540eae779603cc3db84b3986a15ecb5308b54303146eee9837c137b51a…  （1.27-alpine 的 zlib 1.3.1-r2 有
#     CVE-2026-22184 / CVE-2026-85091 两个 HIGH ⇒ 换到已修的 1.3.2-r0 基础镜像）

# ---------- builder：Node 构建静态文件 ----------
FROM node:22-alpine AS builder

WORKDIR /build

COPY web/package.json web/package-lock.json ./

RUN npm ci --omit=dev

COPY web/ ./

RUN npm run build

# ---------- runtime：nginx:alpine 只托管静态文件 ----------
FROM nginx:1.30-alpine AS runtime

# 非 root 运行：nginx 以 nginx 用户启动，须改听 8080（<1024 端口非 root 绑不了），
# 并把 nginx 要写的缓存、运行、日志目录 chown 给 nginx 用户
RUN mkdir -p /var/cache/nginx /var/run /var/log/nginx \
    && chown -R nginx:nginx /var/cache/nginx /var/run /var/log/nginx

COPY web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder --chown=nginx:nginx /build/dist /usr/share/nginx/html

USER nginx

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
