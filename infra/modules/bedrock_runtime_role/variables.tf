variable "project_name" {
  description = "Project name used for resource naming."
  type        = string
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
}

variable "role_name_override" {
  description = "Optional explicit IAM role name. Leave unset to use the generated default."
  type        = string
  default     = null
}

variable "trusted_principal_arns" {
  description = "AWS principal ARNs allowed to assume the runtime role. Leave empty to trust the current AWS account."
  type        = list(string)
  default     = []
}

variable "foundation_model_ids" {
  description = "Bedrock foundation model IDs this role can invoke through Bedrock runtime APIs."
  type        = list(string)
  default     = []
}

variable "inference_profile_arns" {
  description = "Optional Bedrock inference profile ARNs this role can invoke."
  type        = list(string)
  default     = []
}

variable "guardrail_arns" {
  description = "Optional Bedrock guardrail ARNs this role can apply."
  type        = list(string)
  default     = []
}

variable "assets_bucket_arn" {
  description = "ARN of the S3 bucket used for prompt and artifact storage."
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
