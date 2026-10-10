# Budget alerts only notify - they never stop resources. The hard stops are the free-tier limits
# (and, on Azure for Students, the credit's spending limit).
resource "time_static" "budget_start" {}

resource "azurerm_consumption_budget_resource_group" "main" {
  count = length(var.budget_contact_emails) > 0 ? 1 : 0

  name              = local.names.budget
  resource_group_id = azurerm_resource_group.main.id
  amount            = var.budget_amount
  time_grain        = "Monthly"

  time_period {
    # Has to be the first day of a month; pinned at the first apply so later plans stay clean.
    start_date = formatdate("YYYY-MM-01'T'00:00:00'Z'", time_static.budget_start.rfc3339)
  }

  notification {
    threshold      = 50
    threshold_type = "Actual"
    operator       = "GreaterThanOrEqualTo"
    contact_emails = var.budget_contact_emails
  }

  notification {
    threshold      = 100
    threshold_type = "Actual"
    operator       = "GreaterThanOrEqualTo"
    contact_emails = var.budget_contact_emails
  }

  notification {
    threshold      = 100
    threshold_type = "Forecasted"
    operator       = "GreaterThanOrEqualTo"
    contact_emails = var.budget_contact_emails
  }
}
