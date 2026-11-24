variable "region" {
  description = "阿里云地域，如 cn-hangzhou"
  type        = string
  default     = "cn-hangzhou"
}

variable "acr_namespace" {
  description = "ACR 命名空间名，须客户先确认；个人版与企业版共用此名。规则：2–30 字符，小写字母开头，仅含小写字母、数字、中划线。"
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,29}$", var.acr_namespace))
    error_message = "acr_namespace 须为 2–30 字符，小写字母开头，仅含小写字母、数字、中划线。"
  }
}

variable "edition" {
  description = "客户账号开通的 ACR 版本：Personal（个人版）或 Enterprise（企业版）。必填，无默认值，避免未确认版本就创建了个人版资源。"
  type        = string

  validation {
    condition     = contains(["Personal", "Enterprise"], var.edition)
    error_message = "edition 只允许 Personal 或 Enterprise。请先向客户确认版本再填。"
  }
}

variable "instance_type" {
  description = "企业版实例规格（仅 edition = Enterprise 时用）：Basic / Standard / Advanced"
  type        = string
  default     = "Basic"

  validation {
    condition     = contains(["Basic", "Standard", "Advanced"], var.instance_type)
    error_message = "instance_type 只允许 Basic、Standard 或 Advanced。"
  }
}

variable "period" {
  description = "企业版包年包月时长（月，仅 edition = Enterprise 时用）。预付费实例创建时必须设置；年付产品取 12 的整数倍。"
  type        = number
  default     = 1

  validation {
    condition     = contains([1, 2, 3, 6, 12, 24, 36], var.period)
    error_message = "period 只允许 1、2、3、6、12、24、36（月）；年付产品取 12 的整数倍。"
  }
}

variable "confirm_enterprise_period" {
  description = "企业版购买周期确认：edition = Enterprise 时必须显式设为 true，表示已与客户确认 period（月数）无误，避免误购。个人版不用填。"
  type        = bool
  default     = false

  validation {
    condition     = var.edition != "Enterprise" || var.confirm_enterprise_period
    error_message = "Enterprise 模式下请先与客户确认购买周期（period），确认无误后设置 confirm_enterprise_period = true 再执行 apply。"
  }
}
