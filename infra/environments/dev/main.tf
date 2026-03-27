provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile
}

locals {
  common_tags = merge(
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
      Repository  = "hybrid-ai-platform"
    },
    var.tags
  )
}

module "ai_assets_bucket" {
  source = "../../modules/ai_assets_bucket"

  project_name         = var.project_name
  environment          = var.environment
  bucket_name_override = var.ai_assets_bucket_name_override
  force_destroy        = var.ai_assets_bucket_force_destroy
  tags                 = local.common_tags
}

module "observability" {
  source = "../../modules/observability"

  project_name      = var.project_name
  environment       = var.environment
  retention_in_days = var.log_retention_days
  tags              = local.common_tags
}

module "bedrock_runtime_role" {
  source = "../../modules/bedrock_runtime_role"

  project_name           = var.project_name
  environment            = var.environment
  trusted_principal_arns = var.runtime_role_trusted_principal_arns
  foundation_model_ids   = var.bedrock_allowed_model_ids
  inference_profile_arns = var.bedrock_allowed_inference_profile_arns
  guardrail_arns         = var.bedrock_allowed_guardrail_arns
  assets_bucket_arn      = module.ai_assets_bucket.bucket_arn
  log_group_arn          = module.observability.log_group_arn
  tags                   = local.common_tags
}
