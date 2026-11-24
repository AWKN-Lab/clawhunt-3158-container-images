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
