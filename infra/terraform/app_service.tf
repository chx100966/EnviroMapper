# Free F1: shared compute, 60 CPU-minutes/day, 1 GB RAM, 165 MB outbound/day, no Always On -
# the app unloads after ~20 idle minutes and the next request pays a cold start.
resource "azurerm_service_plan" "api" {
  name                = local.names.api_plan
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  os_type             = "Linux"
  sku_name            = "F1"
  tags                = local.tags
}

resource "azurerm_linux_web_app" "api" {
  name                                     = local.names.api_app
  resource_group_name                      = azurerm_resource_group.main.name
  location                                 = azurerm_resource_group.main.location
  service_plan_id                          = azurerm_service_plan.api.id
  https_only                               = true
  ftp_publish_basic_authentication_enabled = false

  identity {
    type = "SystemAssigned"
  }

  site_config {
    always_on  = false # not available on F1
    ftps_state = "Disabled"

    application_stack {
      dotnet_version = var.api_dotnet_version
    }

    cors {
      allowed_origins = [local.frontend_url]
    }
  }

  # Keys map onto backend/src/EnviroMapper.API/appsettings.json ("__" = nesting level).
  app_settings = {
    "ConnectionStrings__DefaultConnection"  = local.key_vault_references["sql-connection-string"]
    "AzureIoTHub__ConnectionString"         = local.key_vault_references["iothub-service-connection"]
    "Jwt__SecretKey"                        = local.key_vault_references["jwt-signing-key"]
    "APPLICATIONINSIGHTS_CONNECTION_STRING" = azurerm_application_insights.main.connection_string
  }

  tags = local.tags
}
