environment = "dev"
region      = "us-east-1"

# Looser tuning in dev to surface false positives early.
content_filter_strengths = {
  HATE          = "MEDIUM"
  INSULTS       = "MEDIUM"
  SEXUAL        = "HIGH"
  VIOLENCE      = "MEDIUM"
  MISCONDUCT    = "MEDIUM"
  PROMPT_ATTACK = "HIGH"
}

denied_topics = {
  investment-advice = {
    definition = "Recommendations or guidance about allocating funds or assets to generate returns."
    examples   = ["Where should I invest my savings?", "Which stocks should I buy?"]
  }
}

log_retention_days = 14

# ---- Runtime gateway (flip enable_gateway on once these are filled in) ----
enable_gateway = false
# vpc_id                  = "vpc-..."
# alb_subnet_ids          = ["subnet-...", "subnet-..."]
# task_subnet_ids         = ["subnet-...", "subnet-..."]
# gateway_ingress_cidrs   = ["10.0.0.0/8"]
# gateway_certificate_arn = "arn:aws:acm:us-east-1:<account-id>:certificate/..."
# api_key_secret_arn      = "arn:aws:secretsmanager:us-east-1:<account-id>:secret:llm-defense/dev/api-key-..."
# model_id                = "<bedrock model or inference profile id>"
# model_resource_arns     = ["arn:aws:bedrock:...:foundation-model/..."]
gateway_desired_count = 1
gateway_min_count     = 1
gateway_max_count     = 2
