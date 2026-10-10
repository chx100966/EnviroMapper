# `terraform test` runs fully offline: every provider is mocked, nothing is created in Azure.
# Guards the cost model from README.md - a paid SKU should be a deliberate change to these tests.

mock_provider "azurerm" {
  # Mocked values still go through azurerm's validation, so IDs need the right shape.
  mock_data "azurerm_client_config" {
    defaults = {
      tenant_id = "00000000-0000-0000-0000-000000000001"
      object_id = "00000000-0000-0000-0000-000000000002"
    }
  }

  mock_resource "azurerm_resource_group" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test"
    }
  }

  mock_resource "azurerm_log_analytics_workspace" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.OperationalInsights/workspaces/log-test"
    }
  }

  mock_resource "azurerm_mssql_server" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.Sql/servers/sql-test"
    }
  }

  mock_resource "azurerm_storage_account" {
    defaults = {
      id                    = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.Storage/storageAccounts/sttest"
      primary_blob_endpoint = "https://sttest.blob.core.windows.net/"
      primary_web_endpoint  = "https://sttest.z1.web.core.windows.net/"
    }
  }

  mock_resource "azurerm_service_plan" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.Web/serverFarms/asp-test"
    }
  }

  mock_resource "azurerm_key_vault" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.KeyVault/vaults/kv-test"
    }
  }
}

mock_provider "azapi" {}

mock_provider "random" {
  mock_resource "random_string" {
    defaults = {
      result = "t3st"
    }
  }
}

mock_provider "time" {
  mock_resource "time_static" {
    defaults = {
      rfc3339 = "2026-10-11T12:00:00Z"
    }
  }
}

run "uses_only_free_or_scale_to_zero_tiers" {
  command = apply

  assert {
    condition     = azurerm_iothub.main.sku[0].name == "F1"
    error_message = "IoT Hub must stay on the free F1 tier."
  }

  assert {
    condition     = azurerm_service_plan.api.sku_name == "F1"
    error_message = "The API must stay on the free App Service F1 plan."
  }

  assert {
    condition     = azurerm_service_plan.functions.sku_name == "FC1" && length(azurerm_function_app_flex_consumption.processor.always_ready) == 0
    error_message = "The Function App must run on Flex Consumption without always-ready (billed) instances."
  }

  assert {
    condition     = azapi_resource.sql_database.body.properties.useFreeLimit && azapi_resource.sql_database.body.properties.freeLimitExhaustionBehavior == "AutoPause"
    error_message = "The database must use the SQL free offer and pause instead of billing when it is used up."
  }

  assert {
    condition     = azurerm_static_web_app.frontend[0].sku_tier == "Free"
    error_message = "The Static Web App must stay on the Free plan."
  }

  assert {
    condition     = azurerm_log_analytics_workspace.main.daily_quota_gb <= 0.16
    error_message = "The Log Analytics daily cap must keep a month under the 5 GB free allowance."
  }

  assert {
    condition     = length(azurerm_consumption_budget_resource_group.main) == 0
    error_message = "No budget is created without contact emails."
  }
}

run "storage_frontend_fallback" {
  command = apply

  variables {
    frontend_hosting = "storage"
  }

  assert {
    condition     = length(azurerm_static_web_app.frontend) == 0 && length(azurerm_storage_account_static_website.frontend) == 1
    error_message = "frontend_hosting = \"storage\" must replace the Static Web App with a storage static website."
  }

  assert {
    condition     = one(azurerm_linux_web_app.api.site_config[0].cors[0].allowed_origins) == output.frontend_url
    error_message = "The API must allow CORS from the frontend URL."
  }
}

run "budget_with_contacts" {
  command = apply

  variables {
    budget_contact_emails = ["team@example.com"]
  }

  assert {
    condition     = azurerm_consumption_budget_resource_group.main[0].time_period[0].start_date == "2026-10-01T00:00:00Z"
    error_message = "The budget must start on the first day of the month of the first apply."
  }
}
