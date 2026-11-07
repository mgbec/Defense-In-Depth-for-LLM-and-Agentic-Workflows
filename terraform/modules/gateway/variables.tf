variable "name_prefix" {
  type = string
}

variable "environment" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "alb_subnet_ids" {
  description = "Subnets for the ALB (public if internet-facing, private if internal)."
  type        = list(string)
}

variable "task_subnet_ids" {
  description = "Private subnets for the Fargate tasks."
  type        = list(string)
}

variable "internal" {
  description = "Create an internal ALB. Strongly preferred when callers are inside your network."
  type        = bool
  default     = true
}

variable "ingress_cidrs" {
  description = "CIDRs allowed to reach the ALB on 443."
  type        = list(string)
}

variable "egress_cidrs" {
  description = "Destinations the tasks may reach on 443. Narrow this to VPC endpoint CIDRs where possible."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "certificate_arn" {
  description = "ACM certificate for the HTTPS listener."
  type        = string
}

variable "ecr_repository_url" {
  type = string
}

variable "image_tag" {
  type = string
}

variable "guardrail_id" {
  type = string
}

variable "guardrail_version" {
  type = string
}

variable "guardrail_arn" {
  type = string
}

variable "model_id" {
  description = "Bedrock model or inference profile ID passed to Converse."
  type        = string
}

variable "model_resource_arns" {
  description = "ARNs the task may invoke. For an inference profile include the profile ARN and the underlying foundation model ARNs in each region it routes to."
  type        = list(string)
}

variable "api_key_secret_arn" {
  description = "Secrets Manager secret holding the gateway bearer token (plain string value)."
  type        = string
}

variable "kms_key_arn" {
  description = "Customer-managed KMS key for the gateway log group. The task execution role is also granted kms:Decrypt on it, for secrets encrypted with the same key."
  type        = string
}

variable "alarm_topic_arn" {
  type    = string
  default = null
}

variable "cpu" {
  description = "Fargate CPU units. ML scanners are CPU-bound; start at 2048."
  type        = number
  default     = 2048
}

variable "memory" {
  description = "Fargate memory in MiB. The transformer models need several GiB."
  type        = number
  default     = 8192
}

variable "desired_count" {
  type    = number
  default = 2
}

variable "min_count" {
  type    = number
  default = 2
}

variable "max_count" {
  type    = number
  default = 6
}

variable "cpu_target_percent" {
  type    = number
  default = 60
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "deletion_protection" {
  type    = bool
  default = true
}

variable "extra_env" {
  description = "Extra container environment variables (for example PII_ENTITIES, INJECTION_THRESHOLD)."
  type        = map(string)
  default     = {}
}

variable "tags" {
  type    = map(string)
  default = {}
}
