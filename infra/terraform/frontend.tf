# React SPA. Static Web Apps Free: 100 GB bandwidth/month, free TLS, preview environments for PRs.
resource "azurerm_static_web_app" "frontend" {
  count = var.frontend_hosting == "static_web_app" ? 1 : 0

  name                = local.names.static_web_app
  resource_group_name = azurerm_resource_group.main.name
  location            = var.static_web_app_location
  sku_tier            = "Free"
  sku_size            = "Free"
  tags                = local.tags
}

# Fallback: static website on the existing storage account ($web container). Works in any region.
resource "azurerm_storage_account_static_website" "frontend" {
  count = var.frontend_hosting == "storage" ? 1 : 0

  storage_account_id = azurerm_storage_account.main.id
  index_document     = "index.html"
  # Client-side routes fall back to the SPA (served with HTTP 404, which browsers render normally).
  error_404_document = "index.html"
}

locals {
  frontend_url = (
    var.frontend_hosting == "static_web_app"
    ? "https://${one(azurerm_static_web_app.frontend[*].default_host_name)}"
    : trimsuffix(azurerm_storage_account.main.primary_web_endpoint, "/")
  )
}
