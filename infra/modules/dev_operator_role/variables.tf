variable "project_name" {
  description = "Short lowercase project name used for naming and tagging."
  type        = string
}

variable "environment" {
  description = "Short lowercase environment name used for naming and tagging."
  type        = string
}

variable "operator_user_name" {
  description = "Existing IAM user name that may assume the operator role."
  type        = string
}

variable "role_name_override" {
  description = "Optional explicit IAM role name override."
  type        = string
  default     = null
}

variable "foundation_model_ids" {
  description = "Bedrock foundation model IDs the operator role may invoke."
  type        = list(string)
  default     = []
}

variable "inference_profile_arns" {
  description = "Optional Bedrock inference profile ARNs the operator role may invoke."
  type        = list(string)
  default     = []
}

variable "guardrail_arns" {
  description = "Optional Bedrock guardrail ARNs the operator role may apply."
  type        = list(string)
  default     = []
}

variable "assets_bucket_arn" {
  description = "ARN of the AI assets S3 bucket."
  type        = string
}

variable "log_group_arn" {
  description = "ARN of the assistant CloudWatch Logs group."
  type        = string
}

variable "enable_observability_access" {
  description = "Grant quota and metric read access for Bedrock troubleshooting."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Additional tags applied to all resources."
  type        = map(string)
  default     = {}
}
