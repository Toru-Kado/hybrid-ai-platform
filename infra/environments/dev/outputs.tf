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
