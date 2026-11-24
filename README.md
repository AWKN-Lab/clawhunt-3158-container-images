# 会员空间平台 · 容器镜像（#3158）

> **交付范围（一半）**：两个 Dockerfile + `image.yml` 工作流 + 本地可跑的验证。
> 镜像构建、Trivy 镜像扫描、推送到客户私有仓库、Terraform 建镜像仓库
> 命名空间——这四步本机做不了（无 docker、无客户凭证），**未执行**，
> 见文末“未执行清单”。不拿一半证据冒充完整交付。

- 问题：容器镜像构建、私有镜像仓库推送与漏洞扫描
- 报价 $94.50，净额 $70.87（报价 × 75%；每单扣 $15 是算错的，作废）
- 统一技术约定：后端 Python 3.11 / FastAPI；工作台 React + TypeScript +
TDesign；配置与密钥只从环境变量读取；只用虚构测试数据。

## 文件

| 文件 | 说明 |
|---|---|
| `app/Dockerfile` | 后端镜像：多阶段，`python:3.11-slim`；runtime 以非 root 用户 `app` 运行；暴露 8000；HEALTHCHECK 探活 `/healthz` |
| `app/main.py` | 后端最小桩：只提供 `/healthz` 与根路径占位，真实后端替换本文件即可 |
| `app/requirements.txt` | 后端桩依赖（fastapi 0.165.0、uvicorn 0.54.0，已 pin） |
| `web/Dockerfile` | 前端镜像：`node:22-alpine` 构建 + `nginx:1.27-alpine` 托管静态文件 |
| `web/nginx.conf` | gzip 开启；SPA 路由回退 `index.html`；`/healthz` 探活 |
| `web/package.json` / `web/scripts/build.mjs` / `web/public/index.html` | 前端最小构建桩（真实前端替换 `public/` 与构建脚本即可） |
| `.dockerignore` | 排除 `.env*`、`.git`、`tests/fixtures`、`node_modules` 等 |
| `.github/workflows/image.yml` | main 合并与打 `v*` tag 时构建；标签为短 SHA 与版本 tag，永不用 latest；推送到客户私有仓库；Trivy 扫描 |
| `tests/` | 本地验收：pytest 静态核验 + 后端本地实测 + 前端构建实测 + Trivy 本地实测 |
| `evidence/` | 实测输出原文 |

## 基础镜像（已核验）

2026-11-24 经 Docker Hub API 核验，三处 tag 均真实存在（amd64）：

| 镜像 | digest 前缀 |
|---|---|
| `python:3.11-slim` | `sha256:b701198cb708…` |
| `node:22-alpine` | `sha256:12f54cafa58d…` |
| `nginx:1.27-alpine` | `sha256:62223d644fa2…` |

## 端口

- 后端：容器内 8000（`uvicorn main:app --host 0.0.0.0 --port 8000`）。
- 前端：容器内 **8080**，不是 80——前端镜像以非 root 用户 `nginx`
运行，绑不了 1024 以下端口；部署层把 8080 映射到 80 即可
（`docker run -p 80:8080 …` 或编排层端口映射）。

## 本地运行与测试

```bash
bash tests/run_all.sh # pytest 20 项 + 后端本地实测 + 前端构建实测 + Trivy 本地实测
```

- pytest：Dockerfile 静态断言（多阶段、非 root、端口、HEALTHCHECK、
不 COPY `.env`）、`.dockerignore` 仿真判定、workflow 静态断言。
- 后端本地实测：起 uvicorn，`GET /healthz` 返回 `{"status":"ok"}`。
- 前端构建实测：`npm ci && npm run build`，`dist/index.html` 存在；
nginx.conf 关键指令逐项 grep 核对（本机无 nginx 二进制，`nginx -t`
未执行）。
- Trivy 本地实测（Trivy 0.76.2 二进制，`$TRIVY` 或 PATH）：
真实依赖 0 漏洞；含 CRITICAL 的样本（`tests/fixtures/vuln-app/`，
pillow 9.5.0，5 个 CRITICAL）以工作流同款参数扫描时 exit 1；
两份 Dockerfile 配置扫描 0 findings。
详见 `ACCEPTANCE.md` 与 `evidence/`。

## CI（`.github/workflows/image.yml`）

触发：push 到 `main` 与打 `v*` tag 时构建并推送；PR 只构建不推送
（`load: true` 载入本地镜像供 Trivy 扫描）。

标签策略：`type=sha,format=short`（`sha-<7 位>`）与
`type=semver,pattern={{version}}`（打 `v*` tag 时）；`flavor: latest=false`
且有守卫步骤拦截 `:latest`。**发布永不用 latest。**

Trivy：两个镜像各扫一次，`severity: CRITICAL,HIGH`，
`exit-code: "1"`——存在 CRITICAL 即失败；SARIF 报告作为 artifact
上传（保留 30 天）。

### 接入前须客户配置（本仓库无任何真实凭证）

| 位置 | 名称 | 内容 |
|---|---|---|
| 仓库 Variables | `ACR_REGISTRY` | 如 `registry.cn-hangzhou.aliyuncs.com` |
| 仓库 Variables | `ACR_NAMESPACE` | 命名空间名，须客户先在 ACR 建好 |
| Environment `prod` secrets | `ACR_USERNAME` / `ACR_PASSWORD` | RAM 子账号，只授 ACR 推送权限 |

## 回滚

镜像按 SHA 标签不可覆盖（须在 ACR 侧开启标签不可变，见下），
保留最近 30 个版本；部署回滚直接指向上一个 SHA 标签，
不用重新构建。

## 未执行清单（须客户凭证 / 有 docker 的环境）

| # | 未执行项 | 原因 | 补齐条件 |
|---|---|---|---|
| 1 | 镜像构建（`docker build`） | 本机无 docker | 有 docker 的机器或 CI 里跑 `image.yml` |
| 2 | 容器内验证（验收 1：`whoami` 输出 `app`；验收 2：解包检查无 `.env`/`.git`） | 同上 | 同上；`USER app` 与 `.dockerignore` 已静态核验（见 `ACCEPTANCE.md`） |
| 3 | Trivy 镜像扫描与报告（验收 4 完整形态） | 同上 | 同上；扫描配置已静态核验，CRITICAL 失败机制已本地验证 |
| 4 | 推送到客户私有仓库、仓库中无 `latest` 标签的核查（验收 3 后半） | 无客户云账号与仓库凭证 | 配好上表三项后由 CI 执行 |
| 5 | Terraform 创建镜像仓库命名空间与 `backend`、`web` 两个私有仓库 | 无客户云账号；且须先确认账号开通的是企业版还是个人版（决定资源写法） | 客户提供账号版本 + 命名空间名后补写 |
| 6 | 推送成功截图与 Trivy 报告 | 依赖 1–4 | 1–4 执行后补进 `evidence/` |

## 对接点

- 后端日志：生产应接 #3190 的结构化日志（单行 JSON 到 stdout、
落盘前脱敏）；本 Dockerfile 已加 `--no-access-log`，
避免 uvicorn 默认访问日志重复出现且未经脱敏。
- `app/main.py` 是桩：真实后端替换它即可，Dockerfile、端口、
探活路径、启动命令均不需改。
- `web/` 是桩：真实前端（React + TypeScript + TDesign）替换
`public/` 与构建脚本即可，Dockerfile 与 nginx 配置不需改。
