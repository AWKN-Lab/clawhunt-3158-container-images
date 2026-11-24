# #3158 验收证据（逐字摘录，CI run 45429409322，提交 babdd36）

以下输出全部逐字摘自首次 CI 的 evidence 作业日志
（https://github.com/AWKN-Lab/clawhunt-3158-container-images/actions/runs/45429409322）。
完整日志与报告文件见该 run 的 artifact `trivy-reports-evidence`。

## AC1：后端容器内 `whoami` 输出 `app`

步骤「验收 1：容器内 whoami 输出 app」：

```
whoami=app
```

## AC2：镜像中不存在 `.env` 文件与 `.git` 目录

步骤「验收 2：镜像内无 .env 与 .git」（逐层解包，`docker save` 后逐个解 `layer.tar`）：

```
ghcr.io/awkn-lab/clawhunt-3158-backend:sha-babdd36 layers clean (解包 8 层)
ghcr.io/awkn-lab/clawhunt-3158-web:sha-babdd36 layers clean (解包 11 层)
```

## AC3：仓库中镜像标签为短 SHA 或版本号，不存在 `latest` 标签

步骤「验收 3：GHCR 仓库无 latest 标签（仅 push 事件）」：
用 GitHub REST Packages API 全量 `--paginate` 列出两仓库全部标签，
逐行 `grep -qx 'latest'`，无命中则通过。实际标签列表（节选）：

```
clawhunt-3158-backend tags:
sha-babdd36
sha-1b42076
sha-c11a12f
sha-a442871
...
clawhunt-3158-web tags:
（同为 sha-*，无 latest）
```

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
