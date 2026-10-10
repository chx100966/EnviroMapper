resource "azurerm_log_analytics_workspace" "main" {
  name                = local.names.log_analytics
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  # Ingestion stops for the rest of the day once the cap is hit - acceptable for a thesis environment.
  daily_quota_gb = var.log_daily_quota_gb
  tags           = local.tags
}

resource "azurerm_application_insights" "main" {
  name                 = local.names.app_insights
  location             = azurerm_resource_group.main.location
  resource_group_name  = azurerm_resource_group.main.name
  workspace_id         = azurerm_log_analytics_workspace.main.id
  application_type     = "web"
  daily_data_cap_in_gb = var.log_daily_quota_gb
  tags                 = local.tags
}
