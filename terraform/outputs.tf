output "acr_namespace" {
  description = "ACR 命名空间名"
  value       = local.namespace_name
}

output "backend_repo" {
  description = "后端镜像仓库名"
  value       = local.is_enterprise ? alicloud_cr_ee_repo.backend[0].name : alicloud_cr_repo.backend[0].name
}

output "web_repo" {
  description = "前端镜像仓库名"
  value       = local.is_enterprise ? alicloud_cr_ee_repo.web[0].name : alicloud_cr_repo.web[0].name
}

output "registry_endpoint" {
  description = "镜像仓库地址：个人版按地域拼；企业版取实例公网（internet）端点的首个域名。"
  value       = var.edition == "Personal" ? "registry.${var.region}.aliyuncs.com" : local.ee_internet_domains[0]

  precondition {
    condition     = var.edition == "Personal" || length(local.ee_internet_domains) > 0
    error_message = "企业版实例未返回公网（internet）端点，请在 ACR 控制台确认实例已开通公网访问后再执行 apply。"
  }
}
