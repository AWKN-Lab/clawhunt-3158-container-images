# #3158 验收证据（逐字摘录，CI run 45440459117，本提交）

以下输出全部逐字摘自本提交 CI 的 evidence 作业日志
（https://github.com/AWKN-Lab/clawhunt-3158-container-images/actions/runs/45440459117）。
完整日志与报告文件见该 run 的 artifact `trivy-reports-evidence`。
三步的完整命令与关键结果的逐字摘录另存为 `evidence/` 下的日志文件
（仅去除行首时间戳与 ANSI 颜色码；原始完整日志见 CI 运行 45440459117）。

## AC1：后端容器内 `whoami` 输出 `app`

步骤「验收 1：容器内 whoami 输出 app」：

```
whoami=app
```

完整命令与关键结果的逐字摘录（含镜像标签与 whoami 结果）见 `evidence/test-whoami-docker.log`（原始完整日志见 CI 运行 45440459117）。

## AC2：镜像中不存在 `.env` 文件与 `.git` 目录

步骤「验收 2：镜像内无 .env 与 .git」（逐层解包，`docker save` 后逐个解 `layer.tar`）：

```
ghcr.io/awkn-lab/clawhunt-3158-backend:sha-259ab24 layers clean (解包 8 层)
ghcr.io/awkn-lab/clawhunt-3158-web:sha-259ab24 layers clean (解包 11 层)
```

完整命令与关键结果的逐字摘录（含容器内 test 与逐层解包全过程）见 `evidence/test-layers-clean.log`（原始完整日志见 CI 运行 45440459117）。

## AC3：仓库中镜像标签为短 SHA 或版本号，不存在 `latest` 标签

步骤「验收 3：GHCR 仓库无 latest 标签（仅 push 事件）」：
用 GitHub REST Packages API 全量 `--paginate` 列出两仓库全部标签，
逐行 `grep -qx 'latest'`，无命中则通过。实际标签列表（全量，两仓库各 14 个）：

```
clawhunt-3158-backend tags:
sha-259ab24
sha-49473e8
sha-dba21b2
sha-babdd36
sha-1b42076
sha-c11a12f
sha-a442871
sha-cb1787f
sha-ed42c79
sha-acabfb4
sha-1f87901
sha-8867722
sha-29a2a54
sha-9d78579
clawhunt-3158-web tags:
sha-259ab24
sha-49473e8
sha-dba21b2
sha-babdd36
sha-1b42076
sha-c11a12f
sha-a442871
sha-cb1787f
sha-ed42c79
sha-acabfb4
sha-1f87901
sha-8867722
sha-29a2a54
sha-9d78579
no latest tag on GHCR: ok
```

完整命令与关键结果的逐字摘录见 `evidence/test-ghcr-tags.log`（原始完整日志见 CI 运行 45440459117）。
客户 ACR 配好后的复核方法见 `README.md`「AC3 复核：客户 ACR 配好后如何核查」。

## AC4：换成含 CRITICAL 漏洞的旧基础镜像时 Trivy 步骤失败

步骤「Trivy 扫描旧基础镜像（预期失败）」以
`--severity CRITICAL --exit-code 1` 扫描旧基础镜像，
步骤「断言旧基础镜像确实被拦截」：

```
vuln-base blocked by Trivy: ok
```

## Trivy 门禁（最终镜像）

步骤「门禁：后端镜像无 CRITICAL/HIGH」与「门禁：前端镜像无 CRITICAL/HIGH」：

```
##[notice]HITS=0
##[notice]HITS=0
```

两镜像 CRITICAL/HIGH 零命中；SARIF 各 0 条结果，JSON 各 0 个漏洞。
