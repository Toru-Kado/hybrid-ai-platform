output "log_group_name" {
  description = "Name of the assistant CloudWatch log group."
  value       = aws_cloudwatch_log_group.assistant.name
}

output "log_group_arn" {
  description = "ARN of the assistant CloudWatch log group."
  value       = aws_cloudwatch_log_group.assistant.arn
}
