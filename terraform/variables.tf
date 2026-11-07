variable "region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  type = string

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be dev or prod."
  }
}

variable "project" {
  type    = string
  default = "llm-defense"
}

variable "guardrail_profile_arn" {
  description = "Guardrail profile ARN to enable STANDARD tier with cross-region inference. Null keeps processing in-region (CLASSIC tier)."
  type        = string
  default     = null
}

variable "content_filter_strengths" {
  type = map(string)
  default = {
    HATE          = "HIGH"
    INSULTS       = "HIGH"
    SEXUAL        = "HIGH"
    VIOLENCE      = "HIGH"
    MISCONDUCT    = "HIGH"
    PROMPT_ATTACK = "HIGH"
  }
}

variable "denied_topics" {
  type = map(object({
    definition = string
    examples   = list(string)
  }))
  default = {}
}

variable "custom_regexes" {
  type = map(object({
    pattern       = string
    description   = string
    input_action  = string
    output_action = string
  }))
  default = {}
}

variable "blocked_words" {
  type    = list(string)
  default = []
}

variable "grounding_thresholds" {
  type    = map(number)
  default = {}
}

variable "enable_invocation_logging" {
  description = "Manage Bedrock model invocation logging. It is a per-account, per-region singleton."
  type        = bool
  default     = true
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "alert_email" {
  type    = string
  default = null
}

variable "waf_associate_arns" {
  description = "ALB or API Gateway stage ARNs to attach the edge WAF to."
  type        = list(string)
  default     = []
}

variable "waf_rate_limit_per_5min" {
  type    = number
  default = 1000
}

variable "waf_max_body_bytes" {
  type    = number
  default = 8192
}

# ------------------------------------------------------------------ gateway service
variable "enable_gateway" {
  description = "Deploy the runtime gateway (ECS Fargate + ALB). Requires the network and image inputs below."
  type        = bool
  default     = false
}

variable "image_tag" {
  description = "Gateway image tag in ECR (the git SHA, set by CI)."
  type        = string
  default     = ""
}

variable "vpc_id" {
  type    = string
  default = ""
}

variable "alb_subnet_ids" {
  type    = list(string)
  default = []
}

variable "task_subnet_ids" {
  type    = list(string)
  default = []
}

variable "gateway_internal" {
  description = "Internal ALB (recommended). Set false only if clients are on the internet."
  type        = bool
  default     = true
}

variable "gateway_ingress_cidrs" {
  type    = list(string)
  default = []
}

variable "gateway_certificate_arn" {
  type    = string
  default = ""
}

variable "model_id" {
  description = "Bedrock model or inference profile ID used by the gateway."
  type        = string
  default     = ""
}

variable "model_resource_arns" {
  description = "ARNs the gateway may invoke (model and, if used, inference profile)."
  type        = list(string)
  default     = []
}

variable "api_key_secret_arn" {
  description = "Secrets Manager secret holding the bearer token clients must present."
  type        = string
  default     = ""
}

variable "gateway_desired_count" {
  type    = number
  default = 2
}

variable "gateway_min_count" {
  type    = number
  default = 2
}

variable "gateway_max_count" {
  type    = number
  default = 6
}

variable "gateway_env" {
  description = "Extra container env vars, e.g. INJECTION_THRESHOLD, PII_ENTITIES, SYSTEM_PROMPT."
  type        = map(string)
  default     = {}
}

variable "redteam_source_cidrs" {
  description = "IPv4 CIDRs of the red-team runner that bypass the WAF. Non-production only (enforced)."
  type        = list(string)
  default     = []
}
