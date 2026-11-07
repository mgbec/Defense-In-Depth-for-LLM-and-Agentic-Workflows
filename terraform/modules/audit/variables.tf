variable "name_prefix" {
  type = string
}

variable "enable_invocation_logging" {
  description = "Manage the account/region-wide Bedrock model invocation logging configuration."
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "Retention for invocation logs, which can contain blocked content in plaintext."
  type        = number
  default     = 30
}

variable "kms_deletion_window_days" {
  type    = number
  default = 30
}

variable "alert_email" {
  description = "Email subscribed to the alerts topic. Subscription must be confirmed manually."
  type        = string
  default     = null
}

variable "tags" {
  type    = map(string)
  default = {}
}
