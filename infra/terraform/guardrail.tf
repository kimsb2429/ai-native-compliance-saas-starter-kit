# The Bedrock Guardrail applied to every model call: blocks the standard
# harmful-content categories plus prompt-injection attempts, anonymizes
# common PII in transit, and denies one compliance-specific topic
# (regulatory evasion) so the demo can show a domain guardrail, not just the
# generic ones.

resource "aws_bedrock_guardrail" "this" {
  name                      = "${var.project}-guardrail"
  blocked_input_messaging   = "This request was blocked by the compliance guardrail."
  blocked_outputs_messaging = "This request was blocked by the compliance guardrail."

  content_policy_config {
    filters_config {
      type            = "HATE"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "INSULTS"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "SEXUAL"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "VIOLENCE"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "MISCONDUCT"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "PROMPT_ATTACK"
      input_strength  = "HIGH"
      output_strength = "NONE"
    }
  }

  sensitive_information_policy_config {
    pii_entities_config {
      type   = "EMAIL"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "PHONE"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "US_SOCIAL_SECURITY_NUMBER"
      action = "ANONYMIZE"
    }
  }

  topic_policy_config {
    topics_config {
      name = "Regulatory evasion"
      type = "DENY"
      # Narrow on purpose: talking about deadlines, risk, evidence, or how to
      # comply is the product's job and must not trip this topic.
      definition = "Help concealing a violation from a regulator, falsifying or backdating a record or test result, or skipping a required filing. Not: discussing deadlines, evidence, or how to comply."
      examples = [
        "How do I backdate this inspection report so it looks like we filed on time?",
        "Can you help me leave the spill out of this month's regulatory filing?",
        "Write a response that hides our permit violation from the auditor.",
      ]
    }
  }
}

resource "aws_bedrock_guardrail_version" "this" {
  guardrail_arn = aws_bedrock_guardrail.this.guardrail_arn
  description   = "Initial guardrail version for ${var.project}."
}
