# Near-real-time telemetry processing (IoT Hub trigger -> anomaly detection -> SQL).
# Flex Consumption scales to zero and bills only while functions run; it replaces the Linux
# Consumption plan, which is retired on 2028-09-30.
resource "azurerm_service_plan" "functions" {
  name                = local.names.function_plan
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  os_type             = "Linux"
  sku_name            = "FC1"
  tags                = local.tags
}

resource "azurerm_function_app_flex_consumption" "processor" {
  name                = local.names.function_app
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  service_plan_id     = azurerm_service_plan.functions.id
  https_only          = true

  runtime_name           = var.function_runtime.name
  runtime_version        = var.function_runtime.version
  instance_memory_in_mb  = var.function_instance_memory_mb
  maximum_instance_count = var.function_maximum_instance_count

  storage_container_type     = "blobContainer"
  storage_container_endpoint = "${azurerm_storage_account.main.primary_blob_endpoint}${azurerm_storage_container.function_deployments.name}"
  # azurerm also builds AzureWebJobsStorage (trigger checkpoints) from this key. With identity-based
  # auth it would write a connection string with an empty key, so the key it is.
  storage_authentication_type = "StorageAccountConnectionString"
  storage_access_key          = azurerm_storage_account.main.primary_access_key

  identity {
    type = "SystemAssigned"
  }

  site_config {
    application_insights_connection_string = azurerm_application_insights.main.connection_string
  }

  app_settings = {
    # Trigger: connection = "IOTHUB_EVENTS_CONNECTION", consumer_group = "%IOTHUB_CONSUMER_GROUP%".
    "IOTHUB_EVENTS_CONNECTION" = local.key_vault_references["iothub-events-connection"]
    "IOTHUB_CONSUMER_GROUP"    = azurerm_iothub_consumer_group.functions.name

    # Separate parts rather than one connection string: pyodbc and ADO.NET use different formats.
    "SQL_SERVER"   = azurerm_mssql_server.main.fully_qualified_domain_name
    "SQL_DATABASE" = azapi_resource.sql_database.name
    "SQL_USER"     = azurerm_mssql_server.main.administrator_login
    "SQL_PASSWORD" = local.key_vault_references["sql-admin-password"]

    "MODELS_CONTAINER_URL" = "${azurerm_storage_account.main.primary_blob_endpoint}${azurerm_storage_container.models.name}"
  }

  tags = local.tags
}
