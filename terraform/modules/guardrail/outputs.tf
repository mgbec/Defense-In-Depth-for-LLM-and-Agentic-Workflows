output "guardrail_id" {
  value = aws_bedrock_guardrail.this.guardrail_id
}

output "guardrail_arn" {
  value = aws_bedrock_guardrail.this.guardrail_arn
}

output "guardrail_version" {
  description = "Numbered (immutable) version that applications should pin to."
  value       = aws_bedrock_guardrail_version.this.version
}
