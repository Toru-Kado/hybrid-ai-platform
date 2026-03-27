output "role_name" {
  description = "IAM role name for local operator access."
  value       = aws_iam_role.this.name
}

output "role_arn" {
  description = "IAM role ARN for local operator access."
  value       = aws_iam_role.this.arn
}
