# One general-purpose account: Function App host storage + deployment packages, AI model
# artefacts, and (optionally) the SPA as a static website. Cost at this scale: cents per month.
resource "azurerm_storage_account" "main" {
  name                            = local.names.storage_account
  resource_group_name             = azurerm_resource_group.main.name
  location                        = azurerm_resource_group.main.location
  account_kind                    = "StorageV2"
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  tags                            = local.tags
}

resource "azurerm_storage_container" "function_deployments" {
  name                  = "function-deployments"
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}

# Trained models exported by ai/ (e.g. ONNX) and loaded by the Function App at startup.
resource "azurerm_storage_container" "models" {
  name                  = "models"
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}
