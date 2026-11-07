locals {
  use_standard_tier = var.guardrail_profile_arn != null
  tier_name         = local.use_standard_tier ? "STANDARD" : "CLASSIC"
}

resource "aws_bedrock_guardrail" "this" {
  name                      = var.name
  description               = var.description
  blocked_input_messaging   = var.blocked_input_message
  blocked_outputs_messaging = var.blocked_output_message
  kms_key_arn               = var.kms_key_arn
  tags                      = var.tags

  dynamic "cross_region_config" {
    for_each = local.use_standard_tier ? [1] : []
    content {
      guardrail_profile_identifier = var.guardrail_profile_arn
    }
  }

  content_policy_config {
    dynamic "filters_config" {
      for_each = var.content_filter_strengths
      content {
        type           = filters_config.key
        input_strength = filters_config.value
        # Prompt attack filtering applies to input only; the API requires NONE for output.
        output_strength = filters_config.key == "PROMPT_ATTACK" ? "NONE" : filters_config.value
      }
    }
    tier_config {
      tier_name = local.tier_name
    }
  }

  dynamic "topic_policy_config" {
    for_each = length(var.denied_topics) > 0 ? [1] : []
    content {
      dynamic "topics_config" {
        for_each = var.denied_topics
        content {
          name       = topics_config.key
          type       = "DENY"
          definition = topics_config.value.definition
          examples   = topics_config.value.examples
        }
      }
      tier_config {
        tier_name = local.tier_name
      }
    }
  }

  sensitive_information_policy_config {
    dynamic "pii_entities_config" {
      for_each = var.pii_entities
      content {
        type           = pii_entities_config.key
        action         = pii_entities_config.value.input_action
        input_action   = pii_entities_config.value.input_action
        output_action  = pii_entities_config.value.output_action
        input_enabled  = true
        output_enabled = true
      }
    }

    dynamic "regexes_config" {
      for_each = var.regexes
      content {
        name           = regexes_config.key
        description    = regexes_config.value.description
        pattern        = regexes_config.value.pattern
        action         = regexes_config.value.input_action
        input_action   = regexes_config.value.input_action
        output_action  = regexes_config.value.output_action
        input_enabled  = true
        output_enabled = true
      }
    }
  }

  dynamic "word_policy_config" {
    for_each = (var.enable_profanity_filter || length(var.blocked_words) > 0) ? [1] : []
    content {
      dynamic "managed_word_lists_config" {
        for_each = var.enable_profanity_filter ? [1] : []
        content {
          type           = "PROFANITY"
          input_action   = "BLOCK"
          output_action  = "BLOCK"
          input_enabled  = true
          output_enabled = true
        }
      }
      dynamic "words_config" {
        for_each = toset(var.blocked_words)
        content {
          text           = words_config.value
          input_action   = "BLOCK"
          output_action  = "BLOCK"
          input_enabled  = true
          output_enabled = true
        }
      }
    }
  }

  dynamic "contextual_grounding_policy_config" {
    for_each = length(var.grounding_thresholds) > 0 ? [1] : []
    content {
      dynamic "filters_config" {
        for_each = var.grounding_thresholds
        content {
          type      = filters_config.key
          threshold = filters_config.value
        }
      }
    }
  }
}

# Immutable, numbered version. Applications should pin to this rather than DRAFT so that
# guardrail changes roll out through a reviewed Terraform apply, not live edits.
resource "aws_bedrock_guardrail_version" "this" {
  guardrail_arn = aws_bedrock_guardrail.this.guardrail_arn
  description   = "Managed by Terraform"
  # Keep prior versions so running applications can roll back or drain gracefully.
  skip_destroy = true

  lifecycle {
    replace_triggered_by = [aws_bedrock_guardrail.this]
  }
}
