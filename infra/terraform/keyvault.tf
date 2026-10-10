resource "random_password" "jwt_signing_key" {
  length  = 64
  special = false
}

resource "azurerm_key_vault" "main" {
  name                       = local.names.key_vault
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  soft_delete_retention_days = 7
  # Off so `terraform destroy` can purge the vault; turn on for anything long-lived.
  purge_protection_enabled = false
  tags                     = local.tags
}

# Lets the identity running Terraform write the secrets below.
resource "azurerm_role_assignment" "kv_deployer" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

# A fresh role assignment takes a while to reach the Key Vault data plane; without the wait the
# first apply tends to fail with 403 ForbiddenByRbac.
resource "time_sleep" "kv_rbac_propagation" {
  create_duration = "60s"
  depends_on      = [azurerm_role_assignment.kv_deployer]
}

locals {
  key_vault_secrets = {
    "sql-admin-password"        = random_password.sql_admin.result
    "sql-connection-string"     = local.sql_connection_string
    "iothub-service-connection" = azurerm_iothub_shared_access_policy.backend.primary_connection_string
    "iothub-events-connection"  = local.iothub_events_connection_string
    "jwt-signing-key"           = random_password.jwt_signing_key.result
  }

  # App Service / Functions resolve these at runtime with the app's managed identity.
  # Versionless URIs always point at the latest secret version.
  key_vault_references = {
    for name, secret in azurerm_key_vault_secret.app :
    name => "@Microsoft.KeyVault(SecretUri=${secret.versionless_id})"
  }
}

resource "azurerm_key_vault_secret" "app" {
  for_each = local.key_vault_secrets

  name         = each.key
  value        = each.value
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [time_sleep.kv_rbac_propagation]
}

resource "azurerm_role_assignment" "kv_api" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_linux_web_app.api.identity[0].principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "kv_function" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_function_app_flex_consumption.processor.identity[0].principal_id
  principal_type       = "ServicePrincipal"
}
