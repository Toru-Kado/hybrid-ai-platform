variable "aws_region" {
  description = "AWS region for the dev environment. Bedrock access must be enabled in this region."
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "Optional AWS CLI profile name used by Terraform."
  type        = string
  default     = null
}

variable "project_name" {
  description = "Short lowercase project name used for naming and tagging."
  type        = string
  default     = "hybrid-ai-platform"

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "project_name must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "environment" {
  description = "Short lowercase environment name used for naming and tagging."
  type        = string
  default     = "dev"

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.environment))
    error_message = "environment must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "ai_assets_bucket_name_override" {
  description = "Optional explicit S3 bucket name for AI assets. Leave unset to let Terraform build a safe default."
  type        = string
  default     = null
}

variable "ai_assets_bucket_force_destroy" {
  description = "Allow S3 bucket deletion even when objects remain. Keep false unless the environment is disposable."
  type        = bool
  default     = false
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention for the assistant log group."
  type        = number
  default     = 14

  validation {
    condition     = var.log_retention_days > 0
    error_message = "log_retention_days must be greater than zero."
  }
}

variable "bedrock_allowed_model_ids" {
  description = "Bedrock foundation model IDs the runtime role may invoke. Keep this list to the models you actually use."
  type        = list(string)
  default     = []
}

variable "bedrock_allowed_inference_profile_arns" {
  description = "Optional Bedrock inference profile ARNs the runtime role may invoke."
  type        = list(string)
  default     = []
}

variable "bedrock_allowed_guardrail_arns" {
  description = "Optional Bedrock guardrail ARNs the runtime role may apply."
  type        = list(string)
  default     = []
}

variable "runtime_role_trusted_principal_arns" {
  description = "AWS principal ARNs allowed to assume the runtime role. Leave empty to trust the current AWS account."
  type        = list(string)
  default     = []
}

variable "operator_user_name" {
  description = "Optional existing IAM user name that should assume a separate local operator role."
  type        = string
  default     = null
}

variable "operator_role_name_override" {
  description = "Optional explicit IAM role name for the local operator role."
  type        = string
  default     = null
}

variable "operator_role_enable_observability_access" {
  description = "Grant Bedrock quota and CloudWatch read access to the local operator role."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Additional tags applied to all resources."
  type        = map(string)
  default     = {}
}
