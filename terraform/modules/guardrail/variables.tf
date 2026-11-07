variable "name" {
  description = "Guardrail name."
  type        = string
}

variable "description" {
  description = "Guardrail description."
  type        = string
  default     = "Managed policy layer (Layer 3) of the LLM defense-in-depth architecture."
}

variable "kms_key_arn" {
  description = "KMS key ARN used to encrypt the guardrail at rest. Null uses an AWS-owned key."
  type        = string
  default     = null
}

variable "guardrail_profile_arn" {
  description = <<-EOT
    Guardrail profile ARN for cross-region inference. When set, the STANDARD tier is used
    (better prompt-attack detection, code-domain support, more languages). When null, the
    CLASSIC tier is used and no cross-region routing occurs (relevant for data residency).
  EOT
  type        = string
  default     = null
}

variable "blocked_input_message" {
  type    = string
  default = "Your request was blocked by our content policy."
}

variable "blocked_output_message" {
  type    = string
  default = "The response was blocked by our content policy."
}

variable "content_filter_strengths" {
  description = "Per-category strength (NONE, LOW, MEDIUM, HIGH) applied to input and output. PROMPT_ATTACK is input-only; output strength is forced to NONE by the API."
  type        = map(string)
  default = {
    HATE          = "HIGH"
    INSULTS       = "HIGH"
    SEXUAL        = "HIGH"
    VIOLENCE      = "HIGH"
    MISCONDUCT    = "HIGH"
    PROMPT_ATTACK = "HIGH"
  }

  validation {
    condition     = alltrue([for k, v in var.content_filter_strengths : contains(["HATE", "INSULTS", "SEXUAL", "VIOLENCE", "MISCONDUCT", "PROMPT_ATTACK"], k) && contains(["NONE", "LOW", "MEDIUM", "HIGH"], v)])
    error_message = "Keys must be valid filter types; values must be NONE, LOW, MEDIUM or HIGH."
  }
}

variable "denied_topics" {
  description = "Topics the application must not discuss."
  type = map(object({
    definition = string
    examples   = list(string)
  }))
  default = {}
}

variable "pii_entities" {
  description = "Map of Bedrock PII entity type to input/output action (BLOCK, ANONYMIZE, NONE)."
  type = map(object({
    input_action  = string
    output_action = string
  }))
  default = {
    AWS_ACCESS_KEY            = { input_action = "BLOCK", output_action = "BLOCK" }
    AWS_SECRET_KEY            = { input_action = "BLOCK", output_action = "BLOCK" }
    PASSWORD                  = { input_action = "BLOCK", output_action = "BLOCK" }
    CREDIT_DEBIT_CARD_NUMBER  = { input_action = "BLOCK", output_action = "BLOCK" }
    US_SOCIAL_SECURITY_NUMBER = { input_action = "BLOCK", output_action = "BLOCK" }
    US_BANK_ACCOUNT_NUMBER    = { input_action = "BLOCK", output_action = "BLOCK" }
    EMAIL                     = { input_action = "ANONYMIZE", output_action = "ANONYMIZE" }
    PHONE                     = { input_action = "ANONYMIZE", output_action = "ANONYMIZE" }
  }
}

variable "regexes" {
  description = "Custom regex entities (for example internal API key formats)."
  type = map(object({
    pattern       = string
    description   = string
    input_action  = string
    output_action = string
  }))
  default = {}
}

variable "blocked_words" {
  description = "Exact-match custom words or phrases to block."
  type        = list(string)
  default     = []
}

variable "enable_profanity_filter" {
  type    = bool
  default = true
}

variable "grounding_thresholds" {
  description = "Contextual grounding thresholds (0-0.99) keyed by GROUNDING or RELEVANCE. Empty disables the check. Only applies when callers supply grounding sources."
  type        = map(number)
  default     = {}
}

variable "tags" {
  type    = map(string)
  default = {}
}
