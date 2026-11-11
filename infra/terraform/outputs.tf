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
