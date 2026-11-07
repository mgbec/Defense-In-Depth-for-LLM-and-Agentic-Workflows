output "kms_key_arn" {
  value = aws_kms_key.this.arn
}

output "alerts_topic_arn" {
  value = aws_sns_topic.alerts.arn
}

output "invocation_log_group_name" {
  value = try(aws_cloudwatch_log_group.invocations[0].name, null)
}
