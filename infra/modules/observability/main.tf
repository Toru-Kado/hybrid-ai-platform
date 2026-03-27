locals {
  sanitized_project_name = replace(lower(var.project_name), "_", "-")
  log_group_name         = "/aws/${local.sanitized_project_name}/${var.environment}/assistant"
}

resource "aws_cloudwatch_log_group" "assistant" {
  name              = local.log_group_name
  retention_in_days = var.retention_in_days

  tags = merge(
    var.tags,
    {
      Name = local.log_group_name
    }
  )
}
