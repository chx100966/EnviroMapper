provider "azurerm" {
  # Subscription comes from ARM_SUBSCRIPTION_ID (see README.md), so nobody commits their own ID.

  # azurerm 5.x registers no resource providers by default and a fresh subscription (e.g. Azure for
  # Students) may not have these yet. Registering needs Owner/Contributor on the subscription.
  resource_provider_registrations = "none"
  resource_providers_to_register = [
    "Microsoft.Consumption",
    "Microsoft.Devices",
    "Microsoft.Insights",
    "Microsoft.KeyVault",
    "Microsoft.OperationalInsights",
    "Microsoft.Sql",
    "Microsoft.Storage",
    "Microsoft.Web",
  ]

  features {
    application_insights {
      # Otherwise Azure adds a "Failure Anomalies" alert rule that OpenTofu doesn't manage and that
      # blocks `tofu destroy` of the resource group.
      disable_generated_rule = true
    }

    log_analytics_workspace {
      permanently_delete_on_destroy = true
    }
  }
}

provider "azapi" {}
