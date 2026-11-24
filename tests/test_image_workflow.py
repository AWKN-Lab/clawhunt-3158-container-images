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
    wf = load_workflow()
    trivys = [s for s in steps_of(wf) if "trivy-action" in str(s.get("uses", ""))]
    assert len(trivys) == 3, "两个表格式扫描 + 一个 SARIF 报告"
    failing = [s for s in trivys if str(s["with"].get("exit-code")) == "1"]
    assert len(failing) == 2, "两个镜像扫描步骤 exit-code 都须为 1"
    for step in failing:
        assert "CRITICAL" in step["with"]["severity"]
        assert "short-sha" in step["with"]["image-ref"], "镜像引用须用短 SHA 标签"


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
    assert "ghcr.io/v2" not in "\n".join(runs), "Registry API 直调已废除，须走 REST API"

    # 验收 4：旧基础镜像扫描预期失败，且须凭报告里的 CRITICAL 认定，不凭退出码
    vuln = [
        s
        for s in steps
        if "trivy-action" in str(s.get("uses", "")) and s.get("continue-on-error") is True
    ]
    assert vuln, "证据作业须有预期失败的旧基础镜像扫描（验收 4）"
    assert vuln[0]["with"].get("format") == "json"
    assert vuln[0]["with"].get("output") == "trivy-vuln.json"
    assert any(
        "steps.trivy-vuln.outcome" in r and "trivy-vuln.json" in r and "CRITICAL" in r
        for r in runs
    ), "断言步骤须同时核对 Trivy 退出状态与报告里的 CRITICAL"

    # 正常扫描：两个镜像都扫 CRITICAL/HIGH，exit-code 1
    scans = [
        s
        for s in steps
        if "trivy-action" in str(s.get("uses", ""))
        and str(s.get("with", {}).get("exit-code")) == "1"
        and s.get("with", {}).get("format") == "table"
    ]
    assert len(scans) == 2, "两个镜像的正常扫描 exit-code 都须为 1"

    # SARIF：前后端各一份
    sarifs = [
        s
        for s in steps
        if "trivy-action" in str(s.get("uses", ""))
        and s.get("with", {}).get("format") == "sarif"
    ]
    assert len(sarifs) == 2, "前后端各需一份 SARIF 报告"
    assert {"trivy-backend.sarif", "trivy-web.sarif"} == {
        s["with"]["output"] for s in sarifs
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


def test_sarif_generated_before_gate_scans_and_always_uploaded():
    # SARIF 须在带失败门禁的扫描之前生成，且上传步骤须 if: always()，
    # 否则扫描一失败报告就丢了。
    wf = load_workflow()
    steps = wf["jobs"]["evidence"]["steps"]
    names = [s.get("name", "") for s in steps]

    def first(pred):
        return next(i for i, s in enumerate(steps) if pred(s))

    sarif_idx = first(lambda s: "trivy-action" in str(s.get("uses", "")) and s.get("with", {}).get("format") == "sarif")
    scan_idx = first(lambda s: "trivy-action" in str(s.get("uses", "")) and str(s.get("with", {}).get("exit-code")) == "1" and s.get("with", {}).get("format") == "table")
    assert sarif_idx < scan_idx, "SARIF 生成须在带失败门禁的扫描之前"
    uploads = [s for s in steps if "upload-artifact" in str(s.get("uses", ""))]
    assert uploads, "须上传 SARIF 报告"
    assert str(uploads[0].get("if", "")) == "always()", "上传步骤须 if: always()，扫描失败时报告仍要保存"
    upload_idx = names.index(uploads[0].get("name", ""))
    assert upload_idx < scan_idx, "上传须在带失败门禁的扫描之前"


def test_terraform_ci_job_exists():
    wf = load_workflow()
    assert "terraform" in wf["jobs"], "须有 Terraform 独立 CI 作业"
    runs = [str(s.get("run") or "") for s in wf["jobs"]["terraform"]["steps"]]
    assert any("terraform fmt -check" in r for r in runs)
    assert any("terraform init -backend=false" in r for r in runs)
    assert any(r.strip() == "terraform validate" for r in runs)
