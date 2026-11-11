data "azurerm_client_config" "current" {}

# Suffix for globally unique names (storage, Key Vault, apps). Stable once in state.
resource "random_string" "suffix" {
  length  = 4
  upper   = false
  special = false
}

locals {
  suffix = random_string.suffix.result
  base   = "${var.project}-${var.environment}"

  # Abbreviations follow the Cloud Adoption Framework (rg-, st, kv-, app-, ...).
  names = {
    resource_group  = "rg-${local.base}"
    log_analytics   = "log-${local.base}"
    app_insights    = "appi-${local.base}"
    storage_account = "st${var.project}${var.environment}${local.suffix}"
    key_vault       = "kv-${var.project}-${local.suffix}"
    api_plan        = "asp-${local.base}-api"
    api_app         = "app-${local.base}-api-${local.suffix}"
    static_web_app  = "stapp-${local.base}"
    budget          = "budget-${local.base}"
  }

  tags = merge({
    project     = var.project
    environment = var.environment
    managed-by  = "opentofu"
  }, var.tags)
}

resource "azurerm_resource_group" "main" {
  name     = local.names.resource_group
  location = var.location
  tags     = local.tags
}
