resource "random_password" "sql_admin" {
  length           = 32
  min_lower        = 1
  min_upper        = 1
  min_numeric      = 1
  min_special      = 1
  override_special = "!#%*-_=+" # no ; ' or " - they break connection strings
}

resource "azurerm_mssql_server" "main" {
  name                         = local.names.sql_server
  resource_group_name          = azurerm_resource_group.main.name
  location                     = azurerm_resource_group.main.location
  version                      = "12.0"
  administrator_login          = "${var.project}_admin"
  administrator_login_password = random_password.sql_admin.result
  minimum_tls_version          = "1.2"

  # Whoever runs `tofu apply` becomes the Entra ID admin, so they can sign in with their Azure
  # account (Azure Data Studio / SSMS / sqlcmd -G) instead of sharing the password. It changes hands
  # when someone else applies - see README.md, "Working as a team".
  azuread_administrator {
    login_username = "tofu-deployer"
    object_id      = data.azurerm_client_config.current.object_id
  }

  tags = local.tags
}

# 0.0.0.0 means "allow Azure services": App Service F1 and Flex Consumption have no fixed outbound
# IPs and no VNet here (private endpoints would cost more than everything else combined).
resource "azurerm_mssql_firewall_rule" "azure_services" {
  name             = "AllowAzureServices"
  server_id        = azurerm_mssql_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

resource "azurerm_mssql_firewall_rule" "developers" {
  for_each = var.sql_firewall_allowed_ips

  name             = "dev-${each.key}"
  server_id        = azurerm_mssql_server.main.id
  start_ip_address = each.value
  end_ip_address   = each.value
}

# Azure SQL free offer: 100,000 vCore-seconds + 32 GB per month, forever. azurerm has no
# argument for it yet (useFreeLimit) and the offer can only be chosen when the database is created,
# hence azapi for this one resource.
resource "azapi_resource" "sql_database" {
  type      = "Microsoft.Sql/servers/databases@2025-01-01"
  name      = local.names.sql_database
  parent_id = azurerm_mssql_server.main.id
  location  = azurerm_resource_group.main.location
  tags      = local.tags

  body = {
    sku = {
      name = var.sql_sku_name
    }
    properties = {
      useFreeLimit = true
      # When the monthly allowance runs out the database pauses until the 1st instead of billing.
      # Switching to "BillOverUsage" later is one-way.
      freeLimitExhaustionBehavior      = "AutoPause"
      autoPauseDelay                   = var.sql_auto_pause_delay_minutes
      minCapacity                      = 0.5
      maxSizeBytes                     = 34359738368 # 32 GB, the free offer limit
      requestedBackupStorageRedundancy = "Local"
      zoneRedundant                    = false
    }
  }
}

locals {
  # ADO.NET format (backend API / EF Core). A serverless database needs up to a minute to resume
  # after auto-pause, so clients also need retry logic (EF Core: EnableRetryOnFailure).
  sql_connection_string = join(";", [
    "Server=tcp:${azurerm_mssql_server.main.fully_qualified_domain_name},1433",
    "Initial Catalog=${azapi_resource.sql_database.name}",
    "User ID=${azurerm_mssql_server.main.administrator_login}",
    "Password=${random_password.sql_admin.result}",
    "Encrypt=True",
    "TrustServerCertificate=False",
    "Connection Timeout=60",
  ])
}
