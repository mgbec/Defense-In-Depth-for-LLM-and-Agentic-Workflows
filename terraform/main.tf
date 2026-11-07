locals {
  name_prefix = "${var.project}-${var.environment}"

  tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# Cross-cutting: KMS, invocation audit logging, alerting.
module "audit" {
  source = "./modules/audit"

  name_prefix               = local.name_prefix
  enable_invocation_logging = var.enable_invocation_logging
  log_retention_days        = var.log_retention_days
  alert_email               = var.alert_email
}

# Layer 3: managed policy enforcement.
module "guardrail" {
  source = "./modules/guardrail"

  name                     = "${local.name_prefix}-guardrail"
  kms_key_arn              = module.audit.kms_key_arn
  guardrail_profile_arn    = var.guardrail_profile_arn
  content_filter_strengths = var.content_filter_strengths
  denied_topics            = var.denied_topics
  regexes                  = var.custom_regexes
  blocked_words            = var.blocked_words
  grounding_thresholds     = var.grounding_thresholds
}

# Layers 1, 2, 4, 5: the gateway service (pre-filter, Presidio, LLM Guard, model, output
# scanning) calling the Layer 3 guardrail. The ECR repository is created by bootstrap/ so
# CI can push an image before the first apply.
data "aws_ecr_repository" "gateway" {
  count = var.enable_gateway ? 1 : 0
  name  = "${var.project}-gateway"
}

module "gateway" {
  count  = var.enable_gateway ? 1 : 0
  source = "./modules/gateway"

  name_prefix = local.name_prefix
  environment = var.environment

  vpc_id          = var.vpc_id
  alb_subnet_ids  = var.alb_subnet_ids
  task_subnet_ids = var.task_subnet_ids
  internal        = var.gateway_internal
  ingress_cidrs   = var.gateway_ingress_cidrs
  certificate_arn = var.gateway_certificate_arn

  ecr_repository_url = data.aws_ecr_repository.gateway[0].repository_url
  image_tag          = var.image_tag

  guardrail_id      = module.guardrail.guardrail_id
  guardrail_version = module.guardrail.guardrail_version
  guardrail_arn     = module.guardrail.guardrail_arn

  model_id            = var.model_id
  model_resource_arns = var.model_resource_arns
  api_key_secret_arn  = var.api_key_secret_arn

  kms_key_arn         = module.audit.kms_key_arn
  alarm_topic_arn     = module.audit.alerts_topic_arn
  log_retention_days  = var.log_retention_days
  deletion_protection = var.environment == "prod"

  desired_count = var.gateway_desired_count
  min_count     = var.gateway_min_count
  max_count     = var.gateway_max_count
  extra_env     = var.gateway_env

  depends_on = [terraform_data.gateway_inputs]
}

# Fails the plan early, with a clear message, if the gateway is enabled but under-configured.
resource "terraform_data" "gateway_inputs" {
  count = var.enable_gateway ? 1 : 0

  lifecycle {
    precondition {
      condition     = var.image_tag != "" && var.model_id != "" && var.vpc_id != "" && var.gateway_certificate_arn != "" && var.api_key_secret_arn != "" && length(var.model_resource_arns) > 0 && length(var.gateway_ingress_cidrs) > 0
      error_message = "enable_gateway requires image_tag, model_id, model_resource_arns, vpc_id, gateway_ingress_cidrs, gateway_certificate_arn and api_key_secret_arn."
    }
  }
}

# Layer 0: edge protection (also protects the gateway load balancer when enabled).
module "edge" {
  source = "./modules/edge"

  name_prefix             = local.name_prefix
  associate_resource_arns = concat(var.waf_associate_arns, module.gateway[*].alb_arn)
  rate_limit_per_5min     = var.waf_rate_limit_per_5min
  max_body_bytes          = var.waf_max_body_bytes
  log_retention_days      = var.log_retention_days
  alarm_topic_arn         = module.audit.alerts_topic_arn
  exempt_source_cidrs     = var.redteam_source_cidrs

  depends_on = [terraform_data.redteam_guard]
}

# Refuses to plan a production WAF that has a bypass rule.
resource "terraform_data" "redteam_guard" {
  lifecycle {
    precondition {
      condition     = var.environment != "prod" || length(var.redteam_source_cidrs) == 0
      error_message = "redteam_source_cidrs bypasses the WAF and must be empty in prod."
    }
  }
}

# Published so applications and the CI regression suite resolve the pinned guardrail
# without coupling to Terraform state.
resource "aws_ssm_parameter" "guardrail_id" {
  name  = "/${var.project}/${var.environment}/guardrail/id"
  type  = "String"
  value = module.guardrail.guardrail_id
}

resource "aws_ssm_parameter" "guardrail_version" {
  name  = "/${var.project}/${var.environment}/guardrail/version"
  type  = "String"
  value = module.guardrail.guardrail_version
}
