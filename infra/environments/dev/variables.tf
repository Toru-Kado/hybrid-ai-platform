variable "aws_region" {
  description = "AWS region for the dev environment."
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "Optional AWS CLI profile name for Terraform operations."
  type        = string
  default     = null
}

variable "project_name" {
  description = "Project name used for naming and tagging."
  type        = string
  default     = "hybrid-ai-platform"
}

variable "environment" {
  description = "Environment name."
  type        = string
  default     = "dev"
}

variable "bucket_name_override" {
  description = "Optional explicit S3 bucket name."
  type        = string
  default     = null
}

variable "force_destroy_assets_bucket" {
  description = "Allow S3 bucket deletion even when objects remain."
  type        = bool
  default     = false
}

variable "log_retention_days" {
  description = "CloudWatch log retention for the assistant log group."
  type        = number
  default     = 14
}

variable "bedrock_foundation_model_ids" {
  description = "Bedrock foundation model IDs the runtime role can invoke."
  type        = list(string)
  default     = []
}

variable "bedrock_inference_profile_arns" {
  description = "Optional Bedrock inference profile ARNs the runtime role can invoke."
  type        = list(string)
  default     = []
}

variable "trusted_principal_arns" {
  description = "AWS principal ARNs allowed to assume the runtime role. Leave empty to trust the current account."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Additional tags applied to all resources."
  type        = map(string)
  default     = {}
}
