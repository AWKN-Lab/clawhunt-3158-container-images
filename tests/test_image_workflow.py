"""#3158 image.yml 工作流静态核验（本机无 GitHub Actions，不真跑 CI）。

核验点：
- 触发：push 到 main 与打 v* tag 时构建；PR 只构建不推送。
- 标签：短 SHA 与版本 tag；latest 被显式禁用且有守卫步骤拦截。
- Trivy：CRITICAL/HIGH 扫两个镜像，exit-code 1（有 CRITICAL 即失败），
  报告作为 artifact 上传。
- 凭证：只来自仓库 Variables 与 Environment secrets，无硬编码。
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github/workflows/image.yml"


def load_workflow() -> dict:
    return yaml.safe_load(WF.read_text(encoding="utf-8"))


def steps_of(wf: dict) -> list[dict]:
    return wf["jobs"]["build"]["steps"]


def test_triggers_main_push_v_tag_and_pr():
    wf = load_workflow()
    # PyYAML 按 YAML 1.1 把 `on:` 读成布尔 True
    on = wf.get("on", wf.get(True))
    assert on["push"]["branches"] == ["main"]
    assert on["push"]["tags"] == ["v*"]
    assert on["pull_request"]["branches"] == ["main"]


def test_no_latest_tag_anywhere_except_guard():
    # latest 只允许出现在两处：metadata-action 的 latest=false，
    # 与守卫步骤里判断用的 ':latest$' / “latest 标签”字样。
    # runs-on 的 ubuntu-latest 是 Runner 镜像，与我们发布的镜像标签无关。
    wf = load_workflow()
    for step in steps_of(wf):
        uses = str(step.get("uses", ""))
        if "metadata-action" in uses:
            assert "latest=false" in step["with"]["flavor"]
            assert "latest" not in step["with"]["tags"]
    text = WF.read_text(encoding="utf-8")
    assert '":latest"' not in text and "value=latest" not in text
    assert "latest=true" not in text


def test_tags_short_sha_and_semver():
    wf = load_workflow()
    metas = [s for s in steps_of(wf) if "metadata-action" in str(s.get("uses", ""))]
    assert len(metas) == 2, "后端与前端各需一个 metadata-action 步骤"
    for step in metas:
        tags = step["with"]["tags"]
        assert "type=sha,format=short" in tags
        assert "type=semver,pattern={{version}}" in tags
        assert "latest=false" in step["with"]["flavor"]


def test_latest_guard_step_exists():
    wf = load_workflow()
    guards = [s for s in steps_of(wf) if "latest" in s.get("name", "")]
    assert guards, "须有拦截 latest 标签的守卫步骤"
    assert ":latest$" in guards[0]["run"]


def test_trivy_blocks_on_critical():
    # 门禁性质不变，实现分两层：build 作业用 CLI --exit-code 1 直接拦；
    # evidence 作业先出 JSON 报告（--exit-code 0），再由 Python 断言
    # CRITICAL/HIGH 命中就 exit 1。两种实现都要断言，不能只测一种。
    wf = load_workflow()
    all_steps = [s for j in wf["jobs"].values() for s in j.get("steps", [])]
    trivys = [s for s in all_steps if "trivy:" in str(s.get("run", ""))]
    assert len(trivys) >= 8, f"须有 build 2 表格扫描 + 2 SARIF + evidence 2 SARIF + 2 JSON + 1 负控，实测 {len(trivys)}"
    # build 作业：两个镜像扫描 exit-code 1、含 CRITICAL、引用短 SHA 标签
    build = wf["jobs"]["build"]["steps"]
    build_scans = [s for s in build if "trivy:" in str(s.get("run", "")) and "--exit-code 1" in str(s.get("run", ""))]
    assert len(build_scans) == 2, "build 作业两个镜像扫描 exit-code 都须为 1"
    for step in build_scans:
        assert "CRITICAL" in step["run"] and "HIGH" in step["run"]
        assert "sha-" in step["run"], "镜像引用须用短 SHA 标签"
    # evidence 作业：两个门禁断言步骤，须检查 CRITICAL/HIGH 并 exit 1
    evidence = wf["jobs"]["evidence"]["steps"]
    gates = [s for s in evidence if str(s.get("name", "")).startswith("门禁")]
    assert len(gates) == 2, "evidence 作业须有两个门禁断言步骤"
    for step in gates:
        run = str(step.get("run", ""))
        assert "CRITICAL" in run and "HIGH" in run, "门禁断言须检查 CRITICAL/HIGH"
        assert "exit 1" in run, "门禁断言命中时必须 exit 1"
    # SARIF 报告步骤须用 --exit-code 0（只出报告，不直接断作业）
    sarifs = [s for s in trivys if "--format sarif" in str(s.get("run", ""))]
    assert sarifs and all("--exit-code 0" in str(s.get("run", "")) for s in sarifs), \
        "SARIF 报告步骤须用 --exit-code 0"


def test_backend_smoke_uvicorn_start_health():
    # 后端冒烟：runtime 移出 setuptools 后，最大的风险是 uvicorn 起不来。
    # 只 import 不够，必须起容器并 curl /healthz（与前端冒烟同款）。
    wf = load_workflow()
    steps = wf["jobs"]["evidence"]["steps"]
    smoke = [s for s in steps if "backend-smoke" in str(s.get("run", ""))]
    assert smoke, "证据作业须有后端冒烟步骤"
    run = str(smoke[0].get("run", ""))
    assert "docker run -d" in run and "18081:8000" in run, "须起后端容器并映射 8000"
    assert "curl -fsS" in run and "healthz" in run, "须 curl 健康接口，失败即失败"


def test_trivy_report_uploaded_as_artifact():
    wf = load_workflow()
    uploads = [s for s in steps_of(wf) if "upload-artifact" in str(s.get("uses", ""))]
    assert uploads, "Trivy 报告须作为 artifact 上传"
    assert "trivy" in uploads[0]["with"]["name"]
    assert "sarif" in uploads[0]["with"]["path"]


def test_credentials_only_from_vars_and_secrets():
    text = WF.read_text(encoding="utf-8")
    assert "vars.ACR_REGISTRY" in text
    assert "vars.ACR_NAMESPACE" in text
    assert "secrets.ACR_USERNAME" in text
    assert "secrets.ACR_PASSWORD" in text
    # 只查非注释行：注释里的示例域名（如 registry.cn-hangzhou…）不算硬编码
    code = "\n".join(
        line for line in text.splitlines() if not line.strip().startswith("#")
    )
    for bad in ("registry.cn-", "aliyuncs.com"):
        assert bad not in code, f"工作流不得硬编码仓库地址：{bad}"


def test_push_only_on_push_event_pr_build_only():
    wf = load_workflow()
    builds = [s for s in steps_of(wf) if "build-push-action" in str(s.get("uses", ""))]
    assert len(builds) == 2
    for step in builds:
        assert "github.event_name == 'push'" in str(step["with"]["push"])
        assert "pull_request" in str(step["with"]["load"])


def test_environment_prod_required():
    wf = load_workflow()
    assert wf["jobs"]["build"]["environment"] == "prod"


def test_build_job_gated_on_acr_config():
    # 客户 ACR 未配置时 build 作业须跳过，否则 push 到 main 一定红；
    # 验收证据由 evidence 作业出。
    wf = load_workflow()
    cond = wf["jobs"]["build"].get("if", "")
    assert "vars.ACR_REGISTRY" in cond
    assert "vars.ACR_NAMESPACE" in cond


def test_evidence_job_covers_acceptance_without_client_credentials():
    # 不依赖客户凭证的验收证据作业：构建、运行、扫描全在 CI 里做，
    # 镜像推 GHCR（短 SHA 标签，永不用 latest）。
    # 断言钉在 run 内容上，不只看步骤名，否则测试通过、实际工作流失效。
    wf = load_workflow()
    assert "evidence" in wf["jobs"], "须有不依赖客户凭证的验收证据作业"
    job = wf["jobs"]["evidence"]
    assert job.get("permissions", {}).get("packages") == "write"
    steps = job["steps"]
    runs = [str(s.get("run") or "") for s in steps]

    # 证据作业绝不能碰客户 ACR 凭证
    assert "vars.ACR" not in yaml.dump(job) and "secrets.ACR" not in yaml.dump(job)

    # 验收 1：真的跑容器并断言 whoami 输出是 app
    assert any(
        "docker run" in r and "whoami" in r and 'test "$out" = "app"' in r
        for r in runs
    ), "验收 1 须实际运行容器并断言 whoami 输出是 app"

    # 验收 2：逐层解包检查，两个镜像都要；Shell 失败不许冒充通过
    layer_checks = [r for r in runs if "layer.tar" in r and "set -euo pipefail" in r]
    assert layer_checks, "验收 2 须逐层解包镜像检查 .env/.git"
    assert layer_checks[0].count("check_layers ghcr.io") == 2, "两个镜像都要逐层检查"
    assert "未发现任何镜像层" in layer_checks[0], "须断言至少发现一个镜像层，避免空循环通过"

    # 验收 3：用 GitHub REST Packages API 查标签，请求失败必须失败
    ac3 = [r for r in runs if "latest" in r and "gh api" in r]
    assert ac3, "验收 3 须用 GitHub REST API 查 GHCR 标签"
    assert "orgs/" in ac3[0] and "grep -qx 'latest'" in ac3[0]
    assert "--paginate" in ac3[0], "GHCR 标签查询须全量分页，否则旧版本里的 latest 会漏掉"
    # owner 是用户账号：先查 users/，再回退 orgs/（两者都要有，缺一不可）
    assert "users/" in ac3[0], "GHCR 包须先按用户账号查 users/ 接口"
    assert ac3[0].index("users/") < ac3[0].index("orgs/"), "须先试 users/ 再回退 orgs/"
    # 异常场景 1：任意一页出现 latest 都必须失败——grep 要对全量分页结果跑
    assert r"""printf '%s\n' "$versions" | grep -qx 'latest'""" in ac3[0], \
        "须对全量分页结果 grep latest，不能只查第一页"
    # 异常场景 2：API 失败、查不到版本、版本为空都不能当成通过
    assert "test -n \"$versions\"" in ac3[0], "版本为空必须失败"
    assert "::error::" in ac3[0] and "exit 1" in ac3[0], "API 失败必须报错退出"
    assert "ghcr.io/v2" not in "\n".join(runs), "Registry API 直调已废除，须走 REST API"

    # 验收 4：旧基础镜像扫描预期失败，且须凭报告里的 CRITICAL 认定，不凭退出码
    vuln = [
        s
        for s in steps
        if s.get("continue-on-error") is True and "trivy-vuln.json" in str(s.get("run", ""))
    ]
    assert vuln, "证据作业须有预期失败的旧基础镜像扫描（验收 4）"
    assert "--format json" in vuln[0]["run"]
    assert "--output trivy-vuln.json" in vuln[0]["run"]
    assert any(
        "steps.trivy-vuln.outcome" in r and "trivy-vuln.json" in r and "CRITICAL" in r
        for r in runs
    ), "断言步骤须同时核对 Trivy 退出状态与报告里的 CRITICAL"

    # 正常扫描：evidence 作业先出 JSON 报告（--exit-code 0），再由门禁断言
    # CRITICAL/HIGH 命中就 exit 1——不能只认 --exit-code 1 的表格扫描。
    json_scans = [
        s
        for s in steps
        if "trivy:" in str(s.get("run", ""))
        and "--format json" in str(s.get("run", ""))
        and ("trivy-backend.json" in str(s.get("run", "")) or "trivy-web.json" in str(s.get("run", "")))
    ]
    assert len(json_scans) == 2, "两个镜像的正常扫描须各出一份 JSON 报告"
    gates = [s for s in steps if str(s.get("name", "")).startswith("门禁")]
    assert len(gates) == 2, "两个镜像须各有一个门禁断言步骤"
    for step in gates:
        run = str(step.get("run", ""))
        assert "CRITICAL" in run and "HIGH" in run, "门禁断言须检查 CRITICAL/HIGH"
        assert "exit 1" in run, "门禁断言命中时必须 exit 1"

    # SARIF：前后端各一份
    sarifs = [
        s
        for s in steps
        if "trivy:" in str(s.get("run", ""))
        and "--format sarif" in str(s.get("run", ""))
    ]
    assert len(sarifs) == 2, "前后端各需一份 SARIF 报告"
    assert {"trivy-backend.sarif", "trivy-web.sarif"} == {
        name
        for s in sarifs
        for name in ("trivy-backend.sarif", "trivy-web.sarif")
        if name in str(s.get("run", ""))
    }

    # 构建：PR 只加载不推送，push 才推送 GHCR
    builds = [s for s in steps if "build-push-action" in str(s.get("uses", ""))]
    image_builds = [
        s
        for s in builds
        if str(s["with"].get("file", "")) in ("app/Dockerfile", "web/Dockerfile")
    ]
    assert len(image_builds) == 2, "后端与前端镜像各需一个构建步骤"
    for step in image_builds:
        assert "ghcr.io" in str(step["with"].get("tags", ""))
        assert "latest" not in str(step["with"].get("tags", ""))
        assert "github.event_name == 'push'" in str(step["with"]["push"])
        assert "pull_request" in str(step["with"]["load"])


def test_web_smoke_nginx_config_start_health():
    # 前端冒烟：apk upgrade 后 nginx 未必能起，必须实测——
    # 配置检查（nginx -t）、版本打印（nginx -v）、起容器并 curl /healthz。
    wf = load_workflow()
    steps = wf["jobs"]["evidence"]["steps"]
    smoke = [s for s in steps if "nginx -t" in str(s.get("run", ""))]
    assert smoke, "证据作业须有前端 nginx 冒烟步骤"
    run = str(smoke[0].get("run", ""))
    assert "nginx -v" in run, "须打印 nginx 版本"
    assert "docker run -d" in run and "healthz" in run, "须起容器并 curl 健康接口"
    assert "curl -fsS" in run, "健康检查须用 curl -fsS，失败即失败"


def test_reports_uploaded_after_json_scans_with_multiline_path():
    # 第七轮 P0-1/P0-2：上传 path 必须是多行列表（两个 pattern 各占一行），
    # 且上传须在 JSON 生成之后、门禁之前。旧写法把两行折成一个字符串
    # "trivy-*.sarif trivy-*.json"，upload-artifact 找不到任何文件。
    wf = load_workflow()
    steps = wf["jobs"]["evidence"]["steps"]

    def first(pred):
        return next(i for i, s in enumerate(steps) if pred(s))

    sarif_idx = first(lambda s: "--format sarif" in str(s.get("run", "")))
    json_idx = first(lambda s: "--format json" in str(s.get("run", "")) and "trivy-" in str(s.get("run", "")))
    upload_idx = first(lambda s: "upload-artifact" in str(s.get("uses", "")))
    gate_idx = first(lambda s: str(s.get("name", "")).startswith("门禁"))
    assert sarif_idx < json_idx < upload_idx < gate_idx, \
        "顺序须是 SARIF 生成 → JSON 生成 → 上传 → 门禁断言"
    # 两处上传的 path 都须是换行分隔的两个 pattern，不能是空格拼成的一个串
    for job in ("build", "evidence"):
        uploads = [s for s in wf["jobs"][job]["steps"] if "upload-artifact" in str(s.get("uses", ""))]
        assert uploads, f"{job} 作业须有上传步骤"
        path = str(uploads[0]["with"]["path"])
        assert "trivy-*.sarif trivy-*.json" not in path, "path 不能是折叠成一个字符串的两个 pattern"
        assert "trivy-*.sarif" in path and "trivy-*.json" in path, "path 须含 SARIF 与 JSON 两种报告"
        assert "\n" in path, "path 须是 YAML 多行列表"
    upload = steps[upload_idx]
    assert str(upload.get("if", "")) == "always()", "上传须 if: always()，门禁失败时报告仍要保存"


def test_gate_zero_hits_use_notice_not_error():
    # 第七轮 P1-1：零命中时不能打 ::error:: 注解（否则每次都红），
    # 有命中才用 ::error::。
    wf = load_workflow()
    steps = wf["jobs"]["evidence"]["steps"]
    gates = [s for s in steps if str(s.get("name", "")).startswith("门禁")]
    assert len(gates) == 2
    for step in gates:
        run = str(step.get("run", ""))
        assert "::notice::" in run, "零命中须用 ::notice::"
        assert "if not h else '::error::'" in run or 'if not h else "::error::"' in run, \
            "有命中时才用 ::error::"
    # SARIF 须在带失败门禁的扫描之前生成，且上传步骤须 if: always()，
    # 否则扫描一失败报告就丢了。
    wf = load_workflow()
    steps = wf["jobs"]["evidence"]["steps"]
    names = [s.get("name", "") for s in steps]

    def first(pred):
        return next(i for i, s in enumerate(steps) if pred(s))

    sarif_idx = first(lambda s: "trivy:" in str(s.get("run", "")) and "--format sarif" in str(s.get("run", "")))
    gate_idx = first(lambda s: str(s.get("name", "")).startswith("门禁"))
    assert sarif_idx < gate_idx, "SARIF 生成须在门禁断言之前"
    uploads = [s for s in steps if "upload-artifact" in str(s.get("uses", ""))]
    assert uploads, "须上传 SARIF 报告"
    assert str(uploads[0].get("if", "")) == "always()", "上传步骤须 if: always()，扫描失败时报告仍要保存"
    upload_idx = names.index(uploads[0].get("name", ""))
    assert upload_idx < gate_idx, "上传须在门禁断言之前"


def test_terraform_ci_job_exists():
    wf = load_workflow()
    assert "terraform" in wf["jobs"], "须有 Terraform 独立 CI 作业"
    runs = [str(s.get("run") or "") for s in wf["jobs"]["terraform"]["steps"]]
    assert any("terraform fmt -check" in r for r in runs)
    assert any("terraform init -backend=false" in r for r in runs)
    assert any(r.strip() == "terraform validate" for r in runs)
