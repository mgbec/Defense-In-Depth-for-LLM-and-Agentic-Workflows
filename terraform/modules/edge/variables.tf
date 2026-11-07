variable "name_prefix" {
  type = string
}

variable "associate_resource_arns" {
  description = "ARNs of ALBs or API Gateway stages to protect. Empty creates the ACL without attaching it."
  type        = list(string)
  default     = []
}

variable "rate_limit_per_5min" {
  description = "Max requests per source IP in a 5 minute window before blocking."
  type        = number
  default     = 1000
}

variable "max_body_bytes" {
  description = "Requests with a larger body (or an oversized body WAF cannot fully inspect) are blocked."
  type        = number
  default     = 8192
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "exempt_source_cidrs" {
  description = <<-EOT
    IPv4 CIDRs that bypass ALL WAF rules. Intended only for a dedicated red-team runner in
    non-production environments: without it the per-IP rate limit blocks the scan and the
    results would measure the WAF instead of the gateway. Keep empty in production.
  EOT
  type        = list(string)
  default     = []
}

variable "blocked_alarm_threshold" {
  type    = number
  default = 500
}

variable "alarm_topic_arn" {
  type    = string
  default = null
}

variable "tags" {
  type    = map(string)
  default = {}
}
