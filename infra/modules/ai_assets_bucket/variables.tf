variable "project_name" {
  description = "Project name used to derive a safe default bucket name."
  type        = string
}

variable "environment" {
  description = "Deployment environment used in the default bucket name."
  type        = string
}

variable "bucket_name_override" {
  description = "Optional explicit S3 bucket name. Use lowercase letters, numbers, periods, and hyphens only."
  type        = string
  default     = null

  validation {
    condition = var.bucket_name_override == null ? true : (
      can(regex("^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$", var.bucket_name_override)) &&
      length(var.bucket_name_override) >= 3 &&
      length(var.bucket_name_override) <= 63 &&
      length(regexall("\\.\\.", var.bucket_name_override)) == 0
    )
    error_message = "bucket_name_override must be a valid S3 bucket name between 3 and 63 characters."
  }
}

variable "force_destroy" {
  description = "Allow deletion of the bucket even when objects remain. Prefer true only for disposable environments."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags applied to the bucket."
  type        = map(string)
  default     = {}
}
