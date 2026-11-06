# `tofu test` runs fully offline: every provider is mocked, nothing is created in Azure.
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

  mock_resource "azurerm_iothub" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.Devices/iotHubs/iot-test"
    }
  }

  # Cosmos DB role assignments only accept UUIDs as principal IDs.
  mock_resource "azurerm_linux_web_app" {
    defaults = {
      identity = {
        principal_id = "00000000-0000-0000-0000-000000000003"
      }
    }
  }

  mock_resource "azurerm_function_app_flex_consumption" {
    defaults = {
      identity = {
        principal_id = "00000000-0000-0000-0000-000000000004"
      }
    }
  }

  mock_resource "azurerm_cosmosdb_account" {
    defaults = {
      id       = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.DocumentDB/databaseAccounts/cosmos-test"
      endpoint = "https://cosmos-test.documents.azure.com:443/"
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

  variables {
    frontend_hosting = "static_web_app"
  }

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
    condition     = azurerm_cosmosdb_account.main.free_tier_enabled && one(azurerm_cosmosdb_account.main.capacity).total_throughput_limit == 1000
    error_message = "Cosmos DB must use the free tier and refuse throughput beyond its 1000 RU/s."
  }

  assert {
    condition     = azurerm_cosmosdb_sql_database.main.throughput <= 1000
    error_message = "The database's shared throughput must stay within the free 1000 RU/s."
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

run "storage_frontend_by_default" {
  command = apply

  assert {
    condition     = length(azurerm_static_web_app.frontend) == 0 && length(azurerm_storage_account_static_website.frontend) == 1
    error_message = "The default frontend_hosting = \"storage\" must use a storage static website, not a Static Web App."
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

run "telemetry_reaches_cosmos_and_the_builtin_endpoint" {
  command = apply

  assert {
    condition     = azurerm_iothub_route.builtin.endpoint_names == tolist(["events"]) && azurerm_iothub_route.builtin.condition == "true" && azurerm_iothub_route.builtin.enabled
    error_message = "Every device message must still reach the built-in endpoint (Function App trigger) once custom routes exist."
  }

  assert {
    condition     = azurerm_iothub_route.cosmos.endpoint_names == tolist([azurerm_iothub_endpoint_cosmosdb_account.telemetry.name]) && azurerm_iothub_route.cosmos.condition == var.telemetry_store_condition
    error_message = "Messages matching telemetry_store_condition must be routed to the Cosmos DB endpoint."
  }

  assert {
    condition     = azurerm_cosmosdb_sql_container.telemetry.partition_key_paths == tolist(["/${azurerm_iothub_endpoint_cosmosdb_account.telemetry.partition_key_name}"])
    error_message = "The container's partition key must be the property IoT Hub fills from the partition key template."
  }

  assert {
    condition     = azurerm_cosmosdb_sql_container.telemetry.default_ttl == null
    error_message = "Raw telemetry must be kept forever unless cosmos_telemetry_ttl_days is set."
  }
}

run "cosmos_serverless_fallback" {
  command = apply

  variables {
    cosmos_capacity_mode      = "serverless"
    cosmos_telemetry_ttl_days = 90
  }

  assert {
    condition     = !azurerm_cosmosdb_account.main.free_tier_enabled && contains([for c in azurerm_cosmosdb_account.main.capabilities : c.name], "EnableServerless")
    error_message = "cosmos_capacity_mode = \"serverless\" must create a serverless account without the free tier."
  }

  assert {
    condition     = length(azurerm_cosmosdb_account.main.capacity) == 0
    error_message = "A serverless account takes no total throughput limit."
  }

  assert {
    condition     = azurerm_cosmosdb_sql_container.telemetry.default_ttl == 90 * 86400
    error_message = "cosmos_telemetry_ttl_days must set the container's default TTL in seconds."
  }
}
