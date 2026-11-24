terraform {
  required_version = ">= 1.5.0"

  required_providers {
    alicloud = {
      source  = "hashicorp/alicloud"
      version = ">= 1.200.0, < 2.0.0"
    }
  }
}
