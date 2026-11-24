# 会员空间平台 · 镜像仓库 Terraform（#3158）
#
# 建两个私有仓库 backend / web（对应 app/Dockerfile 与 web/Dockerfile），
# 命名空间名与版本（个人版 / 企业版）由客户确认后填。
# 凭证绝不进仓库：用环境变量 ALICLOUD_ACCESS_KEY / ALICLOUD_SECRET_KEY
# 或已有 RAM 子账号（只授 ACR 权限）执行。
# 资源名以 provider schema 为准（terraform providers schema 核过）：
# 个人版用 alicloud_cr_namespace / alicloud_cr_repo；
# 企业版用 alicloud_cr_ee_instance / alicloud_cr_ee_namespace / alicloud_cr_ee_repo。
# 标签不可变：企业版由 tag_immutability 写进代码；个人版无对应资源，
# 申请后在 ACR 控制台手工开启。保留最近 30 个版本：企业版由保留规则
# 写进代码；个人版控制台配，见 terraform/README.md。

provider "alicloud" {
  region = var.region
}

locals {
  is_enterprise  = var.edition == "Enterprise"
  namespace_name = local.is_enterprise ? alicloud_cr_ee_namespace.enterprise[0].name : alicloud_cr_namespace.personal[0].name
  instance_id    = local.is_enterprise ? alicloud_cr_ee_instance.this[0].id : null
  # 企业版公网端点域名（ACR API 的 endpoint_type = "internet"），供 CI 与客户推送用；
  # 个人版不建实例时为空列表，不触发索引错误。
  ee_internet_domains = local.is_enterprise ? flatten([
    for ep in alicloud_cr_ee_instance.this[0].instance_endpoints :
    [for d in ep.domains : d.domain if ep.endpoint_type == "internet"]
  ]) : []
}

# 企业版实例（个人版不建）
resource "alicloud_cr_ee_instance" "this" {
  count         = local.is_enterprise ? 1 : 0
  instance_name = "${var.acr_namespace}-acr"
  instance_type = var.instance_type
  payment_type  = "Subscription" # 企业版实例只支持包年包月；按量计费不被 Provider 接受
  period        = var.period

  lifecycle {
    prevent_destroy = true # 订阅实例不可只靠 terraform destroy 释放，见 README“销毁说明”
  }
}

# 个人版命名空间
resource "alicloud_cr_namespace" "personal" {
  count              = local.is_enterprise ? 0 : 1
  name               = var.acr_namespace
  auto_create        = false
  default_visibility = "PRIVATE"
}

# 企业版命名空间
resource "alicloud_cr_ee_namespace" "enterprise" {
  count              = local.is_enterprise ? 1 : 0
  instance_id        = alicloud_cr_ee_instance.this[0].id
  name               = var.acr_namespace
  auto_create        = false
  default_visibility = "PRIVATE"
}

# 个人版仓库
resource "alicloud_cr_repo" "backend" {
  count     = local.is_enterprise ? 0 : 1
  namespace = local.namespace_name
  name      = "backend"
  summary   = "会员空间平台后端镜像（#3158）"
  repo_type = "PRIVATE"
}

resource "alicloud_cr_repo" "web" {
  count     = local.is_enterprise ? 0 : 1
  namespace = local.namespace_name
  name      = "web"
  summary   = "会员空间平台工作台前端镜像（#3158）"
  repo_type = "PRIVATE"
}

# 企业版保留策略：每个仓库保留最近 30 个版本（个人版无对应资源，控制台配）
resource "alicloud_cr_artifact_lifecycle_rule" "backend" {
  count               = local.is_enterprise ? 1 : 0
  instance_id         = local.instance_id
  namespace_name      = local.namespace_name
  repo_name           = "backend"
  auto                = true
  retention_tag_count = 30

  depends_on = [alicloud_cr_ee_repo.backend]
}

resource "alicloud_cr_artifact_lifecycle_rule" "web" {
  count               = local.is_enterprise ? 1 : 0
  instance_id         = local.instance_id
  namespace_name      = local.namespace_name
  repo_name           = "web"
  auto                = true
  retention_tag_count = 30

  depends_on = [alicloud_cr_ee_repo.web]
}

# 企业版仓库（标签不可变写进代码，回滚靠 SHA 标签）
resource "alicloud_cr_ee_repo" "backend" {
  count            = local.is_enterprise ? 1 : 0
  instance_id      = local.instance_id
  namespace        = local.namespace_name
  name             = "backend"
  summary          = "会员空间平台后端镜像（#3158）"
  repo_type        = "PRIVATE"
  tag_immutability = true
}

resource "alicloud_cr_ee_repo" "web" {
  count            = local.is_enterprise ? 1 : 0
  instance_id      = local.instance_id
  namespace        = local.namespace_name
  name             = "web"
  summary          = "会员空间平台工作台前端镜像（#3158）"
  repo_type        = "PRIVATE"
  tag_immutability = true
}
