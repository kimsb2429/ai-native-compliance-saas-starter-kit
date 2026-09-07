# Optional monthly cost guardrail: alerts budget_alert_email at 80% of actual
# spend. Only created when an email is supplied, since a demo repo shouldn't
# force a budget notification onto someone who hasn't given an address.

resource "aws_budgets_budget" "this" {
  count = var.budget_alert_email != "" ? 1 : 0

  name              = "${var.project}-monthly-budget"
  budget_type       = "COST"
  limit_amount      = tostring(var.budget_limit_usd)
  limit_unit        = "USD"
  time_unit         = "MONTHLY"
  time_period_start = "2025-01-01_00:00"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_alert_email]
  }
}
