locals {
  managed_rules = {
    common = {
      name     = "AWSManagedRulesCommonRuleSet"
      priority = 20
    }
    known_bad_inputs = {
      name     = "AWSManagedRulesKnownBadInputsRuleSet"
      priority = 30
    }
  }
}

# Layer 0: cheapest rejection point. Rate limiting, body size caps, known-bad inputs.
resource "aws_wafv2_web_acl" "this" {
  name        = "${var.name_prefix}-edge"
  description = "Layer 0 edge protection for LLM endpoints"
  scope       = "REGIONAL"
  tags        = var.tags

  default_action {
    allow {}
  }

  rule {
    name     = "max-body-size"
    priority = 5

    action {
      block {}
    }

    statement {
      size_constraint_statement {
        comparison_operator = "GT"
        size                = var.max_body_bytes

        field_to_match {
          body {
            oversize_handling = "MATCH"
          }
        }

        text_transformation {
          priority = 0
          type     = "NONE"
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name_prefix}-max-body-size"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "rate-limit-per-ip"
    priority = 10

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = var.rate_limit_per_5min
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name_prefix}-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  dynamic "rule" {
    for_each = local.managed_rules
    content {
      name     = rule.value.name
      priority = rule.value.priority

      override_action {
        none {}
      }

      statement {
        managed_rule_group_statement {
          name        = rule.value.name
          vendor_name = "AWS"
        }
      }

      visibility_config {
        cloudwatch_metrics_enabled = true
        metric_name                = "${var.name_prefix}-${rule.key}"
        sampled_requests_enabled   = true
      }
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${var.name_prefix}-edge"
    sampled_requests_enabled   = true
  }
}

resource "aws_wafv2_web_acl_association" "this" {
  for_each = toset(var.associate_resource_arns)

  resource_arn = each.value
  web_acl_arn  = aws_wafv2_web_acl.this.arn
}

# WAF requires the log group name to start with aws-waf-logs-.
# checkov:skip=CKV_AWS_158: WAF log delivery to a CMK-encrypted group needs extra key policy; logs hold request metadata with Authorization redacted.
resource "aws_cloudwatch_log_group" "waf" {
  name              = "aws-waf-logs-${var.name_prefix}"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "waf_logs" {
  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.waf.arn}:*"]
    principals {
      type        = "Service"
      identifiers = ["delivery.logs.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_cloudwatch_log_resource_policy" "waf" {
  policy_name     = "${var.name_prefix}-waf-logs"
  policy_document = data.aws_iam_policy_document.waf_logs.json
}

resource "aws_wafv2_web_acl_logging_configuration" "this" {
  resource_arn            = aws_wafv2_web_acl.this.arn
  log_destination_configs = [aws_cloudwatch_log_group.waf.arn]

  redacted_fields {
    single_header {
      name = "authorization"
    }
  }

  redacted_fields {
    single_header {
      name = "cookie"
    }
  }

  depends_on = [aws_cloudwatch_log_resource_policy.waf]
}

resource "aws_cloudwatch_metric_alarm" "blocked_spike" {
  alarm_name          = "${var.name_prefix}-waf-blocked-spike"
  alarm_description   = "Unusual volume of requests blocked at the edge (possible abuse or probing)."
  namespace           = "AWS/WAFV2"
  metric_name         = "BlockedRequests"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 2
  threshold           = var.blocked_alarm_threshold
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_topic_arn == null ? [] : [var.alarm_topic_arn]

  dimensions = {
    WebACL = aws_wafv2_web_acl.this.name
    Region = data.aws_region.current.region
    Rule   = "ALL"
  }

  tags = var.tags
}

data "aws_region" "current" {}
