variable "project_name" {
  description = "Project name used in the CloudWatch log group path."
  type        = string
}

variable "environment" {
  description = "Deployment environment used in the CloudWatch log group path."
  type        = string
}

variable "retention_in_days" {
  description = "CloudWatch Logs retention period in days."
  type        = number
  default     = 14
}

variable "tags" {
  description = "Tags applied to the log group."
  type        = map(string)
  default     = {}
}
