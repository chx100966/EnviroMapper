# Free tier: 8,000 messages/day (metered in 0.5 KB chunks, reset at 00:00 UTC), 500 devices,
# one F1 hub per subscription. F1 can't be upgraded in place - moving to B1/S1 means a new hub.
resource "azurerm_iothub" "main" {
  name                = local.names.iothub
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  sku {
    name     = "F1"
    capacity = 1
  }

  # Built-in Event Hub-compatible endpoint; F1 supports 2 partitions.
  event_hub_partition_count   = 2
  event_hub_retention_in_days = 1

  tags = local.tags
}

# Dedicated reader for the Function App; $Default stays free for `az iot hub monitor-events` etc.
resource "azurerm_iothub_consumer_group" "functions" {
  name                   = "functions"
  iothub_name            = azurerm_iothub.main.name
  eventhub_endpoint_name = "events"
  resource_group_name    = azurerm_resource_group.main.name
}

# Least-privilege keys instead of the built-in iothubowner.
resource "azurerm_iothub_shared_access_policy" "backend" {
  name                = "backend-api"
  resource_group_name = azurerm_resource_group.main.name
  iothub_name         = azurerm_iothub.main.name

  registry_read   = true # list devices
  registry_write  = true # register devices from the API
  service_connect = true # cloud-to-device messages, twins
}

resource "azurerm_iothub_shared_access_policy" "telemetry_reader" {
  name                = "telemetry-reader"
  resource_group_name = azurerm_resource_group.main.name
  iothub_name         = azurerm_iothub.main.name

  service_connect = true # read device-to-cloud messages from the built-in endpoint
}

locals {
  # Event Hubs-style connection string for the built-in endpoint - what the Event Hubs/IoT Hub
  # trigger and the Event Hubs SDKs expect.
  iothub_events_connection_string = join(";", [
    "Endpoint=${azurerm_iothub.main.event_hub_events_endpoint}",
    "SharedAccessKeyName=${azurerm_iothub_shared_access_policy.telemetry_reader.name}",
    "SharedAccessKey=${azurerm_iothub_shared_access_policy.telemetry_reader.primary_key}",
    "EntityPath=${azurerm_iothub.main.event_hub_events_path}",
  ])
}

# --- Message routing ------------------------------------------------------------------------------

# As soon as any custom route exists, IoT Hub stops delivering to the built-in endpoint on its own
# (only messages matching no route still get there through the fallback route). This route keeps
# every message on it for the Function App and `az iot hub monitor-events`.
resource "azurerm_iothub_route" "builtin" {
  name                = "telemetry-to-builtin"
  resource_group_name = azurerm_resource_group.main.name
  iothub_name         = azurerm_iothub.main.name
  source              = "DeviceMessages"
  condition           = "true"
  endpoint_names      = ["events"]
  enabled             = true
}

# Key-based: identity-based auth would need a Cosmos DB data role for the hub's managed identity,
# assigned and propagated before the endpoint is usable. The keys stay in the state and the hub.
resource "azurerm_iothub_endpoint_cosmosdb_account" "telemetry" {
  name                = "cosmos-telemetry"
  resource_group_name = azurerm_resource_group.main.name
  iothub_id           = azurerm_iothub.main.id

  endpoint_uri   = azurerm_cosmosdb_account.main.endpoint
  primary_key    = azurerm_cosmosdb_account.main.primary_key
  secondary_key  = azurerm_cosmosdb_account.main.secondary_key
  database_name  = azurerm_cosmosdb_sql_database.main.name
  container_name = azurerm_cosmosdb_sql_container.telemetry.name

  partition_key_name     = local.cosmos_telemetry_partition_key
  partition_key_template = "{deviceid}-{YYYY}-{MM}"
}

# Ingest validation: only messages matching the condition are stored. Without contentType
# application/json and contentEncoding UTF-8 IoT Hub can't read the body, the condition is false,
# and the message only goes to the built-in endpoint.
resource "azurerm_iothub_route" "cosmos" {
  name                = "telemetry-to-cosmos"
  resource_group_name = azurerm_resource_group.main.name
  iothub_name         = azurerm_iothub.main.name
  source              = "DeviceMessages"
  condition           = var.telemetry_store_condition
  endpoint_names      = [azurerm_iothub_endpoint_cosmosdb_account.telemetry.name]
  enabled             = true
}
