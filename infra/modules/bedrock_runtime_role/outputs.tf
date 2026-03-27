output "role_name" {
  description = "Name of the runtime IAM role."
  value       = aws_iam_role.this.name
}

output "role_arn" {
  description = "ARN of the runtime IAM role."
  value       = aws_iam_role.this.arn
}
