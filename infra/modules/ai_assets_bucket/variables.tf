variable "project_name" {
  description = "Project name used for resource naming."
  type        = string
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
}

variable "bucket_name_override" {
  description = "Optional explicit bucket name."
  type        = string
  default     = null
}

variable "force_destroy" {
  description = "Allow bucket deletion even when objects remain. Useful for dev environments."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags applied to the bucket."
  type        = map(string)
  default     = {}
}
