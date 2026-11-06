# Raw device telemetry. IoT Hub writes it here through message routing (iothub.tf), so storing
# readings needs no code and never wakes the serverless SQL database.
#
# Free tier: the first 1000 RU/s and 25 GB of the account are free for its whole lifetime, but only
# one account per subscription gets it and only when it is created. The fallback is a serverless
# account (billed per request, nothing while idle) - provisioned throughput outside the free tier
# costs at least 400 RU/s, about $23 per month.
locals {
  cosmos_serverless = var.cosmos_capacity_mode == "serverless"

  # Property that IoT Hub fills from the endpoint's partition key template (iothub.tf).
  cosmos_telemetry_partition_key = "partitionKey"

  # Built-in data-plane roles. Cosmos DB has its own RBAC for data, separate from Azure roles.
  cosmos_data_reader_role = "${azurerm_cosmosdb_account.main.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000001"
}

resource "azurerm_cosmosdb_account" "main" {
  name                = local.names.cosmos_account
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  offer_type          = "Standard" # NoSQL API (kind GlobalDocumentDB, the default)
  free_tier_enabled   = !local.cosmos_serverless
  minimal_tls_version = "Tls12"
  # Account keys stay on: the IoT Hub routing endpoint authenticates with them.

  consistency_policy {
    consistency_level = "Session"
  }

  # One region without zone redundancy - every extra region bills its RU/s and storage again.
  geo_location {
    location          = azurerm_resource_group.main.location
    failover_priority = 0
    zone_redundant    = false
  }

  # Hard cost guard: Azure refuses any database, container or region that would take the account
  # over the free 1000 RU/s. Serverless accounts don't support a limit (and don't need one).
  dynamic "capacity" {
    for_each = local.cosmos_serverless ? [] : [1]
    content {
      total_throughput_limit = 1000
    }
  }

  dynamic "capabilities" {
    for_each = local.cosmos_serverless ? ["EnableServerless"] : []
    content {
      name = capabilities.value
    }
  }

  # Default periodic backup (every 4 h, 2 copies kept) - the two copies are free.

  tags = local.tags
}

resource "azurerm_cosmosdb_sql_database" "main" {
  name                = local.names.cosmos_database
  resource_group_name = azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.main.name
  # Shared by all containers in the database (up to 25), so new containers stay within the free tier.
  throughput = local.cosmos_serverless ? null : var.cosmos_database_throughput
}

resource "azurerm_cosmosdb_sql_container" "telemetry" {
  name                = "telemetry"
  resource_group_name = azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.main.name
  database_name       = azurerm_cosmosdb_sql_database.main.name

  # One logical partition per device and month ({deviceid}-{YYYY}-{MM}), far below the 20 GB limit
  # of a logical partition. The partition key can't be changed once the container exists.
  partition_key_paths   = ["/${local.cosmos_telemetry_partition_key}"]
  partition_key_version = 2

  # null = documents never expire.
  default_ttl = var.cosmos_telemetry_ttl_days == null ? null : var.cosmos_telemetry_ttl_days * 86400
}

# Both apps read telemetry with their managed identity - no Cosmos DB key in their settings.
resource "azurerm_cosmosdb_sql_role_assignment" "api" {
  resource_group_name = azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.main.name
  role_definition_id  = local.cosmos_data_reader_role
  principal_id        = azurerm_linux_web_app.api.identity[0].principal_id
  scope               = azurerm_cosmosdb_account.main.id
}

resource "azurerm_cosmosdb_sql_role_assignment" "function" {
  resource_group_name = azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.main.name
  role_definition_id  = local.cosmos_data_reader_role
  principal_id        = azurerm_function_app_flex_consumption.processor.identity[0].principal_id
  scope               = azurerm_cosmosdb_account.main.id
}
