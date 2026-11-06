data "azurerm_client_config" "current" {}

# Suffix for globally unique names (IoT Hub, SQL, storage, Key Vault, apps). Stable once in state.
resource "random_string" "suffix" {
  length  = 4
  upper   = false
  special = false
}

locals {
  suffix = random_string.suffix.result
  base   = "${var.project}-${var.environment}"

  # Abbreviations follow the Cloud Adoption Framework (rg-, iot-, sql-, st, kv-, app-, func-, ...).
  names = {
    resource_group  = "rg-${local.base}"
    log_analytics   = "log-${local.base}"
    app_insights    = "appi-${local.base}"
    iothub          = "iot-${local.base}-${local.suffix}"
    sql_server      = "sql-${local.base}-${local.suffix}"
    sql_database    = "sqldb-${var.project}"
    storage_account = "st${var.project}${var.environment}${local.suffix}"
    key_vault       = "kv-${var.project}-${local.suffix}"
    api_plan        = "asp-${local.base}-api"
    api_app         = "app-${local.base}-api-${local.suffix}"
    function_plan   = "asp-${local.base}-func"
    function_app    = "func-${local.base}-${local.suffix}"
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
