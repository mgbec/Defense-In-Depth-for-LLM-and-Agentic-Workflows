output "guardrail_id" {
  value = module.guardrail.guardrail_id
}

output "guardrail_version" {
  value = module.guardrail.guardrail_version
}

output "guardrail_arn" {
  value = module.guardrail.guardrail_arn
}

output "web_acl_arn" {
  value = module.edge.web_acl_arn
}

output "alerts_topic_arn" {
  value = module.audit.alerts_topic_arn
}

output "gateway_alb_dns_name" {
  description = "DNS name of the gateway load balancer (point your friendly DNS name at this)."
  value       = try(module.gateway[0].alb_dns_name, null)
}
