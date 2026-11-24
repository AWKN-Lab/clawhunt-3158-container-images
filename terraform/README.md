# Terraform：镜像仓库（#3158）

建 ACR 命名空间 + `backend` / `web` 两个私有仓库。
对应 `.github/workflows/image.yml` 里 `build` 作业的推送目标。

## 用之前先确认（问客户的三件事）

1. 账号开通的是个人版还是企业版 → 填 `edition`（`Personal` / `Enterprise`）。
2. 命名空间名 → 填 `acr_namespace`（须客户先想好，建好后改名麻烦）。
3. 地域 → `region`，默认 `cn-hangzhou`，客户账号在哪个地域就填哪个。

## 执行

```bash
cd terraform
export ALICLOUD_ACCESS_KEY=...        # RAM 子账号，只授 ACR 权限
export ALICLOUD_SECRET_KEY=...
terraform init
terraform plan -var acr_namespace=<命名空间名> -var edition=<Personal|Enterprise>
terraform apply -var acr_namespace=<命名空间名> -var edition=<Personal|Enterprise>
```

企业版执行时须另加购买周期确认门：`-var period=<月数> -var confirm_enterprise_period=true`。
不加确认变量，`plan`/`apply` 会被变量校验拦住，避免误购一个月实例。
企业版 `registry_endpoint` 输出取实例公网（`internet`）端点的首个域名；
若实例未开通公网访问，输出的前置检查会报错，请先在控制台开通。

凭证只走环境变量，绝不写进仓库。执行完把输出里的仓库地址填到
GitHub 仓库 Variables（`ACR_REGISTRY` / `ACR_NAMESPACE`），
再把推送账号密码放进 Environment `prod` 的 secrets
（`ACR_USERNAME` / `ACR_PASSWORD`），CI 的 `build` 作业才会跑；
没配之前 `build` 作业自动跳过，验收证据由 `evidence` 作业出。

## 控制台手工项

- 企业版人工前置步骤（Terraform 做不了）：先在企业版控制台设置仓库密码，
  否则命名空间/仓库创建后无法登录推送。
- 销毁说明：企业版实例已加 `prevent_destroy`，直接 `terraform destroy`
  会被拦住。订阅实例不能假定 Terraform 删除资源就能释放云资源：
  到期/退订走阿里云控制台与工单流程，销毁前先在控制台确认实例状态与费用，
  再单独处理状态文件。
- 保留规则实测提醒：企业版保留规则写的是每仓库保留最近 30 个标签，
  `terraform validate` 只能证明符合 Schema，须等真实 apply 后在控制台核对。
- 个人版：两个仓库开启**标签不可变**、保留最近 30 个版本（Terraform
  没有对应资源）。企业版这两项已写进代码（`tag_immutability` 与保留规则）。
- 注意：provider 自 v1.276.0 起把个人版两个资源
  （`alicloud_cr_namespace` / `alicloud_cr_repo`）标为 deprecated，
  建议改用企业版资源；目前仍可用，`terraform validate` 只报警告。
  **个人版不是长期稳定方案**：客户若在个人版上长期用，改版或迁移到企业版时
  资源模型会变，须另行评估，不要把个人版写进长期承诺。
