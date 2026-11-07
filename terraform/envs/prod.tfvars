environment = "prod"
region      = "us-east-1"

denied_topics = {
  investment-advice = {
    definition = "Recommendations or guidance about allocating funds or assets to generate returns."
    examples   = ["Where should I invest my savings?", "Which stocks should I buy?"]
  }
}

# Uncomment to enable the STANDARD tier (cross-region inference). Confirm this is acceptable
# for your data residency requirements first, then supply the profile ARN for your region.
# guardrail_profile_arn = "arn:aws:bedrock:us-east-1:<account-id>:guardrail-profile/us.guardrail.v1:0"

log_retention_days = 30
# alert_email      = "security@example.com"

# ---- Runtime gateway (flip enable_gateway on once these are filled in) ----
enable_gateway = false
# vpc_id                  = "vpc-..."
# alb_subnet_ids          = ["subnet-...", "subnet-..."]
# task_subnet_ids         = ["subnet-...", "subnet-..."]
# gateway_ingress_cidrs   = ["10.0.0.0/8"]
# gateway_certificate_arn = "arn:aws:acm:us-east-1:<account-id>:certificate/..."
# api_key_secret_arn      = "arn:aws:secretsmanager:us-east-1:<account-id>:secret:llm-defense/prod/api-key-..."
# model_id                = "<bedrock model or inference profile id>"
# model_resource_arns     = ["arn:aws:bedrock:...:foundation-model/..."]
gateway_desired_count = 2
gateway_min_count     = 2
gateway_max_count     = 6
