output "ai_assets_bucket_name" {
  description = "S3 bucket name for prompts, datasets, exports, and other AI assets."
  value       = module.ai_assets_bucket.bucket_name
}

output "assistant_log_group_name" {
  description = "CloudWatch log group name for the assistant runtime."
  value       = module.observability.log_group_name
}

output "assistant_runtime_role_arn" {
  description = "IAM role ARN for Bedrock-powered assistant workloads."
  value       = module.bedrock_runtime_role.role_arn
}

output "aws_region" {
  description = "AWS region used by the dev environment."
  value       = var.aws_region
}

output "developer_operator_role_arn" {
  description = "IAM role ARN for local operator access. Null when operator_user_name is unset."
  value       = try(module.dev_operator_role[0].role_arn, null)
}

output "developer_operator_role_name" {
  description = "IAM role name for local operator access. Null when operator_user_name is unset."
  value       = try(module.dev_operator_role[0].role_name, null)
}
