output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "api_url" {
  value = "https://${azurerm_linux_web_app.api.default_hostname}"
}

output "api_app_name" {
  value = azurerm_linux_web_app.api.name
}

output "frontend_url" {
  value = local.frontend_url
}

output "function_app_name" {
  value = azurerm_function_app_flex_consumption.processor.name
}

output "iothub_name" {
  value = azurerm_iothub.main.name
}

output "iothub_hostname" {
  description = "Devices connect here after provisioning through DPS, which returns this hostname."
  value       = azurerm_iothub.main.hostname
}

output "dps_name" {
  value = azurerm_iothub_dps.main.name
}

output "dps_id_scope" {
  description = "Devices register at global.azure-devices-provisioning.net with this ID scope."
  value       = azurerm_iothub_dps.main.id_scope
}

output "dps_enrollment_key_secrets" {
  description = "Key Vault secret holding each enrollment group's key, by group."
  value       = local.dps_enrollment_key_secret_names
}

output "sql_server_fqdn" {
  value = azurerm_mssql_server.main.fully_qualified_domain_name
}

output "sql_database_name" {
  value = azapi_resource.sql_database.name
}

output "cosmos_account_name" {
  value = azurerm_cosmosdb_account.main.name
}

output "cosmos_endpoint" {
  description = "Raw telemetry: database cosmos_database_name, container \"telemetry\"."
  value       = azurerm_cosmosdb_account.main.endpoint
}

output "cosmos_database_name" {
  value = azurerm_cosmosdb_sql_database.main.name
}

output "key_vault_name" {
  value = azurerm_key_vault.main.name
}

output "storage_account_name" {
  value = azurerm_storage_account.main.name
}

output "static_web_app_deployment_token" {
  description = "Put into the GitHub secret used by the Static Web Apps deploy action. Null with frontend_hosting = \"storage\"."
  value       = one(azurerm_static_web_app.frontend[*].api_key)
  sensitive   = true
}
