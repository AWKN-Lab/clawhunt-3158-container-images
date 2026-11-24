"""#3158 Terraform 静态核验（不连阿里云，只读 .tf 文本）。

钉住 GPT 复核的 Terraform 整改点：
- 企业版计费只支持 Subscription，PayAsYouGo 不许出现。
- edition 必填，无默认值。
- 变量校验：命名空间格式、实例规格、时长。
- 企业版实例 prevent_destroy。
- registry_endpoint 输出真实域名，不许留“见控制台”占位文字。
"""

from pathlib import Path

TF = Path(__file__).resolve().parent.parent / "terraform"


def read(name: str) -> str:
    return (TF / name).read_text(encoding="utf-8")


def test_no_pay_as_you_go_anywhere():
    for f in TF.glob("*.tf"):
        assert "PayAsYouGo" not in f.read_text(encoding="utf-8"), (
            f"{f.name} 不得含 PayAsYouGo"
        )


def test_enterprise_payment_type_is_subscription():
    main = read("main.tf")
    assert 'payment_type  = "Subscription"' in main
    assert "var.payment_type" not in main


def test_edition_is_required_without_default():
    variables = read("variables.tf")
    edition = variables.split('variable "edition"')[1].split('variable "')[0]
    assert "default" not in edition, "edition 须必填，无默认值"


def test_variable_validations():
    variables = read("variables.tf")
    assert "^[a-z][a-z0-9-]{1,29}$" in variables, "须校验命名空间格式"
    assert '"Basic"' in variables and '"Standard"' in variables
    assert '"Advanced"' in variables
    assert "contains([1, 2, 3, 6, 12, 24, 36], var.period)" in variables


def test_enterprise_instance_prevent_destroy():
    main = read("main.tf")
    block = main.split('resource "alicloud_cr_ee_instance"')[1].split('resource "')[0]
    assert "prevent_destroy = true" in block


def test_registry_endpoint_is_real_domain():
    outputs = read("outputs.tf")
    assert "见 ACR 控制台" not in outputs
    assert "ee_internet_domains" in outputs
    assert "instance_endpoints" in read("main.tf")


def test_lifecycle_rules_depend_on_repos():
    main = read("main.tf")
    for repo in ("backend", "web"):
        block = main.split(f'resource "alicloud_cr_artifact_lifecycle_rule" "{repo}"')[1].split('resource "')[0]
        assert f"depends_on = [alicloud_cr_ee_repo.{repo}]" in block, (
            f"{repo} 的保留规则须依赖同名仓库，否则首次并行 apply 可能先建规则后建仓库"
        )


def test_enterprise_period_confirmation_gate():
    variables = read("variables.tf")
    assert 'variable "confirm_enterprise_period"' in variables
    assert "var.edition != \"Enterprise\" || var.confirm_enterprise_period" in variables


def test_registry_endpoint_prefers_internet_with_precondition():
    outputs = read("outputs.tf")
    assert "ee_internet_domains" in outputs
    assert 'endpoint_type == "internet"' in read("main.tf")
    assert "precondition" in outputs
    assert "未返回公网" in outputs


def test_both_edition_branches_present():
    main = read("main.tf")
    for resource in (
        "alicloud_cr_namespace",
        "alicloud_cr_repo",
        "alicloud_cr_ee_instance",
        "alicloud_cr_ee_namespace",
        "alicloud_cr_ee_repo",
        "alicloud_cr_artifact_lifecycle_rule",
    ):
        assert f'resource "{resource}"' in main, f"缺 {resource} 资源分支"
    assert "tag_immutability = true" in main
    assert "retention_tag_count = 30" in main
