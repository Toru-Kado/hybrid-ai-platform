variable "project_name" {
  description = "Project name used for resource naming."
  type        = string
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
}

variable "role_name_override" {
  description = "Optional explicit IAM role name."
  type        = string
  default     = null
}

variable "trusted_principal_arns" {
  description = "Principals that can assume the runtime role. Defaults to the current AWS account root."
  type        = list(string)
  default     = []
}

variable "foundation_model_ids" {
  description = "Bedrock foundation model IDs this role can invoke."
  type        = list(string)
  default     = []
}

variable "inference_profile_arns" {
  description = "Optional Bedrock inference profile ARNs this role can invoke."
  type        = list(string)
  default     = []
}

variable "assets_bucket_arn" {
  description = "ARN of the S3 bucket used for AI assets."
  type        = string
}

variable "log_group_arn" {
  description = "ARN of the CloudWatch log group for assistant logs."
  type        = string
}

variable "tags" {
  description = "Tags applied to the IAM role."
  type        = map(string)
  default     = {}
}
