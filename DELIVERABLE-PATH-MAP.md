# 交付物路径对照表（DELIVERABLE PATH MAP）

> **为什么有这张表**：投标时提交的第一版提案里写的是"计划中的文件路径"；本仓落地时
> 部分文件做了更准确的命名或换了位置（**同一实现**），另有**一项未做**（见下）。
> 买家若按提案里的路径找会找不到，本表给出**一一对应**与**未做项**。
>
> - 提案原文（第一版，也是**平台现行版本**）：`proposals/3158-proposal.md`
>   （`sha256` 未变，本单尚未做过提案修订）
> - 逐条验收对照见 `ACCEPTANCE.md`；实测日志见 `evidence/`
>
> ⚠️ **交付状态提示**：本仓当前为**部分交付**（镜像构建 / 推送流水线 / Trivy 扫描 /
> 本地验证已具备；私有镜像仓库的实际创建与推送尚未在真实 registry 上执行）。
> 未完成项见第四节。

## 一、路径对照

| 提案里写的路径 | 本仓实际路径 | 说明 |
|---|---|---|
| `.github/workflows/image.yml` | `.github/workflows/image.yml` | 同名：main 合并与打 `v*` tag 时构建；标签 = git 短 SHA + 版本 tag；**不用 latest**；Trivy 扫描，**存在 CRITICAL 即失败**，报告作 artifact |
| `docker/backend.Dockerfile` | `app/Dockerfile` | 后端镜像构建文件（提案里的 `docker/` 前缀未使用） |
| `docker/web.Dockerfile` | `web/Dockerfile` | 前端镜像构建文件 |
| `scripts/verify_image.sh` | **本仓无 `scripts/` 目录** ⇒ `tests/run_all.sh`（编排）+ `tests/test_trivy_local.sh` + `tests/test_dockerfiles.py` + `tests/test_image_workflow.py` | 镜像合规检查拆成**可单跑的测试**而不是一个 shell 脚本：whoami / 无 `.env` 无 `.git` / 无 `latest` 标签 / CRITICAL 失败 |
| `docs/push-and-trivy-evidence.md` | **本仓无 `docs/` 目录** ⇒ `evidence/test-trivy-local.log`、`evidence/test-backend-local.log`、`evidence/test-web-build.log`、`evidence/test-pytest.log` | 证据改为**原始日志**（未包装成 Markdown 叙述） |
| `tests/fixtures` | `tests/fixtures/Dockerfile.vuln-base`、`tests/fixtures/vuln-app/requirements.txt` | 同名：负控用脆弱基础镜像（触发 CRITICAL 的那条路径） |
| `terraform/` | **未入库** ⇒ 见第四节"未做项" | 私有镜像仓库的创建编排 |

## 二、提案未列、但本仓实际提供

| 路径 | 用途 |
|---|---|
| `ACCEPTANCE.md` | 逐条 AC ↔ 实现 ↔ 复跑命令 ↔ 实测输出 |
| `app/main.py`、`app/requirements.txt` | 后端服务本体（供镜像内自检） |
| `web/nginx.conf`、`web/scripts/build.mjs`、`web/public/index.html`、`web/package.json` | 前端静态站点与构建脚本 |
| `.dockerignore` | 排除 `.env*`、`.git`、`tests/fixtures`、`node_modules` |

## 三、复跑命令（与提案一致）

```bash
bash tests/run_all.sh   # pytest 20 项 + 后端本地实测 + 前端构建实测 + Trivy 本地实测
```

## 四、未做项（如实标注，不假装做了）

| 提案里写的 | 状态 | 原因与现状 |
|---|---|---|
| `terraform/`（创建镜像仓库命名空间与两个私有仓库 `backend` / `web`） | **未做** | 需要**真实私有镜像仓库的凭证与可写权限**（本交付环境不具备，且属客户侧资源）。仓内已具备**推送到既有私有仓库**的流水线与标签/扫描策略；**仓库的创建编排需在客户账号内用 Terraform 另行执行**，本仓不代做，也未以任何方式模拟其结果 |
| 推送真实私有仓库的实跑证据 | **未做** | 同上（无真实 registry 凭证）。已交付的是：本地 Trivy 实测（含负控）、镜像构建实测、workflow 中的推送与扫描步骤 |

## 五、变更说明

本表为**新增说明文件**，不改动任何实现、workflow 或证据。
本仓**没有** `MANIFEST.sha256`（提案亦未承诺清单文件），故无需重算清单。
