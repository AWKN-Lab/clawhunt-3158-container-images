# 验收对照（#3158）

状态说明：**通过** = 按验收标准完整执行；**本地等价通过** = 本机无 docker，
用等价手段验证了同一结论，镜像内的最终验证仍待补；**未执行** = 本机
做不了，写明原因与补齐条件，不冒充。

## 验收 1：`docker run` 后端镜像后在容器内执行 `whoami` 输出 `app`

**未执行**（本机无 docker，无法 `docker run`）。

本地已验证的部分（`tests/test_dockerfiles.py`，见 `evidence/test-pytest.log`）：

- `app/Dockerfile` 含 `useradd -r -u 10001 -g app app` 与 `USER app`，
  且 `USER app` 在 `COPY` 应用文件与 `CMD` 之前生效；
- `COPY --chown=app:app app/main.py`，应用文件属主为 `app`；
- 启动命令 `uvicorn main:app --host 0.0.0.0 --port 8000 --no-access-log`
  已本地实测跑通（`evidence/test-backend-local.log`，`/healthz` 返回
  `{"status":"ok"}`）。

补齐：在有 docker 的环境跑
`docker run --rm <registry>/<ns>/backend:sha-<短 SHA> whoami`，输出应为 `app`。

## 验收 2：解包检查镜像中不存在 `.env` 文件与 `.git` 目录（附命令输出）

**本地等价通过**（镜像解包未执行，见下）。

- `.dockerignore` 仿真判定（`test_dockerignore_excludes_secrets_git_fixtures_modules`，
  20 项 pytest 之一）：仿真构建上下文里 `.env`、`.env.local`、`.git/HEAD`、
  `tests/fixtures/sample.json`、`node_modules/pkg/index.js` 全部被排除，
  `app/main.py`、`app/requirements.txt`、`web/Dockerfile`、`web/nginx.conf`
  全部保留；
- 两份 Dockerfile 逐行审计：没有任何 `COPY` / `ADD` 指令涉及 `.env`
  或 `.git`（`test_backend_does_not_copy_env` 等）；
- `.dockerignore` 含范围要求的四项：`.env*`、`.git`、`tests/fixtures`、
  `node_modules`。

补齐：构建出镜像后跑
`docker run --rm <backend 镜像> sh -c 'ls -a /app; test ! -e /app/.env && echo no-env'`
与 `docker save … | tar -t | grep -E '(\.env|\.git)'`，应无输出。

## 验收 3：仓库中镜像标签为短 SHA 或版本号，不存在 `latest` 标签

**本地等价通过**（仓库实际标签状态未执行，见下）。

- 工作流静态核验（`tests/test_image_workflow.py`）：两个
  `metadata-action` 步骤的标签只含 `type=sha,format=short` 与
  `type=semver,pattern={{version}}`，`flavor: latest=false`；
  另有守卫步骤，标签列表出现 `:latest` 即失败；
  工作流全文无 `:latest`、`value=latest`、`latest=true`。
- Trivy 扫描步骤引用的镜像标签为 `sha-<7 位短 SHA>`，
  与 metadata-action 的短 SHA 生成规则一致（已修掉一次
  全量 SHA 引用错误）。

补齐：首次推送后在客户 ACR 控制台（或 `docker buildx imagetools inspect`
等）核查 `backend`、`web` 两仓库的标签列表，确认无 `latest`；
截图补进 `evidence/`。

## 验收 4：换成含 CRITICAL 漏洞的旧基础镜像时 Trivy 步骤失败

**未执行**（镜像扫描本身未执行）；**失败机制已本地验证**。

- 工作流静态核验：两个镜像扫描步骤 `severity: CRITICAL,HIGH`、
  `exit-code: "1"`、`ignore-unfixed: true`，即 Trivy 发现 CRITICAL
  或 HIGH 即让步骤失败。
- 机制实测（`tests/test_trivy_local.sh`，Trivy 0.76.2，
  见 `evidence/test-trivy-local.log`）：用工作流同款参数
  （`--severity CRITICAL --exit-code 1`）扫描含 CRITICAL 漏洞的样本
  `tests/fixtures/vuln-app/`（pillow 9.5.0，5 个 CRITICAL，
  含 CVE-2023-50447）时 exit 1；真实依赖 `app/requirements.txt`
  扫描 0 漏洞，exit 0。
- 触发样本：`tests/fixtures/Dockerfile.vuln-base`
 （`FROM python:3.7-slim`，2023-06-27 已 EOL，带未修复 CVE）。

补齐：在有 docker 的环境把后端 `FROM` 换成 `python:3.7-slim` 后
重新构建并跑工作流，Trivy 步骤应失败；再换回 `python:3.11-slim`。

## 附加验证（超出验收标准，实测发现并修掉的问题）

1. Trivy 配置扫描（`trivy config`）初版报 `web/Dockerfile` 有 1 个 HIGH
  （DS-0002：未指定非 root USER）。已修复：前端镜像改以 `nginx`
   用户运行、改听 8080（非 root 绑不了 80）、缓存/运行/日志目录
   chown 给 `nginx`；复扫两份 Dockerfile 均为 0 findings。
2. 工作流初版 Trivy 步骤引用了 `sha-<全量 40 位 SHA>`，与
   metadata-action 生成的短 SHA 标签对不上。已修复：加
   `short-sha` 步骤取 `${GITHUB_SHA::7}`，三处 Trivy 引用统一用它。
3. 本地总跑 `tests/run_all.sh`：**ALL PASS**
   （pytest 20 passed；后端本地实测、前端构建实测、Trivy 本地实测全过）。
