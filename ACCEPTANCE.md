# #3158 验收记录（ACCEPTANCE）

订单 #3158：企业空间 · 容器镜像构建与漏洞扫描
提交：`babdd36`（main）
首次 CI：run [45429409322](https://github.com/AWKN-Lab/clawhunt-3158-container-images/actions/runs/45429409322)
（2026-11-24 23:46–23:48 CST，evidence + terraform 全绿；build 作业按设计跳过——无客户 ACR 变量）

## 平台验收 4 项（全部通过，CI 实测）

### AC1：后端容器内 `whoami` 输出 `app`

- CI 步骤「验收 1：容器内 whoami 输出 app」：`whoami=app`，通过。
- 镜像：`ghcr.io/awkn-lab/clawhunt-3158-backend:sha-babdd36`。

### AC2：镜像中不存在 `.env` 文件与 `.git` 目录（附命令输出）

- CI 步骤「验收 2：镜像内无 .env 与 .git」：逐层解包检查，
  后端 `layers clean (解包 8 层)`，前端 `layers clean (解包 11 层)`，
  两镜像均无 `.env` 与 `.git`，通过。

### AC3：仓库中镜像标签为短 SHA 或版本号，不存在 `latest` 标签

- 镜像标签：`sha-babdd36`（短 SHA），另有版本 tag 机制（v* tag 触发时打版本 tag）。
  仓库中无 `latest` 标签。
- CI 步骤「验收 3：GHCR 仓库无 latest 标签（仅 push 事件）」：
  先查 `users/<owner>` 再回退 `orgs/`，全量 `--paginate`，
  对全部分页结果 `grep -qx 'latest'`，通过。

### AC4：换成含 CRITICAL 漏洞的旧基础镜像时 Trivy 步骤失败

- CI 步骤「Trivy 扫描旧基础镜像（预期失败）」：
  旧基础镜像（tests/fixtures/Dockerfile.vuln-base）以
  `--severity CRITICAL --exit-code 1` 扫描，预期失败；
  步骤「断言旧基础镜像确实被拦截」输出
  `vuln-base blocked by Trivy: ok`，通过。

## Trivy 扫描结果（最终镜像）

- 后端：`HITS=0`（CRITICAL/HIGH 零命中），SARIF 0 条结果。
- 前端：`HITS=0`（CRITICAL/HIGH 零命中），SARIF 0 条结果。
- 证据：CI artifact `trivy-reports-evidence`（64,414 字节，4 个文件）：
  `trivy-backend.sarif`、`trivy-web.sarif`、
  `trivy-backend.json`、`trivy-web.json`
  （JSON 报告各 0 个漏洞）。
- 修复链：后端 setuptools/wheel 在 COPY 之后整包删除
  （find_spec 自证 `setuptools` 与 `wheel` 均不在镜像里）；
  前端 nginx:1.30-alpine（zlib 1.3.2-r1）。

## 九项首次 CI 验收

| # | 标准 | 结果 |
|---|------|------|
| 1 | PR 构建通过，GHCR 无写入 | 通过（PR run 45430219811：evidence + terraform 全绿；全程 0 次 GHCR 推送） |
| 2 | Push 构建通过，两个镜像推送成功 | 通过（两镜像已推 GHCR，sha-babdd36） |
| 3 | 两个容器实际运行验收 | 通过（后端 whoami=app；前后端冒烟 curl /healthz 成功） |
| 4 | 镜像逐层检查 .env、.git | 通过（后端 8 层、前端 11 层 clean） |
| 5 | 正常 Trivy CRITICAL/HIGH 失败门禁 | 通过（两镜像 HITS=0，门禁逻辑实测） |
| 6 | 旧基础镜像被 Trivy 拦截 | 通过（vuln-base blocked: ok） |
| 7 | 两份 SARIF 成功生成并保存 | 通过（artifact 4 文件，2 SARIF + 2 JSON） |
| 8 | GHCR 全量分页检查，无 latest | 通过（users 优先 + orgs 回退 + --paginate） |
| 9 | Terraform CI 通过 | 通过（terraform 作业 success） |

第 1 项说明：PR run 45430219811 实测通过（PR #1，分支 `docs/acceptance-ci-evidence`，
提交 8d07d08）：evidence 作业全绿，PR 运行日志中 0 行 `pushing layers` /
`pushing manifest`，镜像只在本地构建（`sha-8845119`），未写入 GHCR。
此前“待验证”是因为当时只做了静态核验（tests 断言 PR 只加载不推送）；
现已由 PR run 实测闭合，九项 9/9。

第 5 项限定：HITS=0 是 CI run 45429409322 当时的结论，绑定当时的基础镜像
digest 与 Trivy DB；基础镜像用浮动 tag（`python:3.11-slim`），
按当前 HEAD 重建复扫会得到不同结果（2026-11-25 复扫命中 `zlib1g` HIGH，
CVE-2026-85091）。复算须 pin digest + 记 Trivy DB 时间戳（见 pitfalls 75）。

## 附加验证（超出验收标准，实测发现并修掉的问题）

1. Trivy 配置扫描（`trivy config`）初版报 `web/Dockerfile` 有 1 个 HIGH
   （DS-0002：未指定非 root USER）。已修复：前端镜像改以 `nginx`
   用户运行、改听 8080（非 root 绑不了 80）、缓存/运行/日志目录
   chown 给 `nginx`；复扫两份 Dockerfile 均为 0 findings。
2. 工作流初版 Trivy 步骤引用了 `sha-<全量 40 位 SHA>`，与
   metadata-action 生成的短 SHA 标签对不上。已修复：加
   `short-sha` 步骤取 `${GITHUB_SHA::7}`，三处 Trivy 引用统一用它。
3. 首次 CI 前的三轮并行推送与复核（第五至九轮）：修掉上游
   fastapi 自证位置错误、AC3 续行符语法错误、setuptools 被 COPY
   带回 runtime、upload-artifact 路径折叠、JSON 先于上传的顺序问题、
   nginx pid 目录符号链接权限问题；全部以 CI 实测收口。
4. 本地总跑 `tests/run_all.sh`：**ALL PASS**
   （pytest 39 passed；后端本地实测、前端构建实测、Trivy 本地实测全过）。
