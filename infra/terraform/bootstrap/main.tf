data "azurerm_client_config" "current" {}

data "azurerm_subscription" "current" {}

resource "random_string" "suffix" {
  length  = 4
  upper   = false
  special = false
}

# --- Team access -----------------------------------------------------------------------------------

# Guests get an email; until they accept it they can't sign in, but their roles already exist.
resource "azuread_invitation" "team" {
  for_each = { for key, m in var.team_members : key => m if m.invite }

  user_email_address = each.value.email
  redirect_url       = "https://portal.azure.com/${data.azurerm_client_config.current.tenant_id}"

  # Without a message block Entra ID creates the guest but sends no email.
  message {
    language = "en-US"
  }
}

data "azuread_user" "team" {
  for_each = { for key, m in var.team_members : key => m if !m.invite }

  mail = each.value.email
}

locals {
  team_object_ids = merge(
    { for key, inv in azuread_invitation.team : key => inv.user_id },
    { for key, user in data.azuread_user.team : key => user.object_id },
  )

  team_roles = merge([
    for key, m in var.team_members : {
      for role in m.roles : "${key}/${role}" => { member = key, role = role }
    }
  ]...)

  # Data-plane roles that Owner doesn't include, for the whole team and whoever runs this.
  everyone = merge(local.team_object_ids, { deployer = data.azurerm_client_config.current.object_id })
}

resource "azurerm_role_assignment" "team" {
  for_each = local.team_roles

  scope                = data.azurerm_subscription.current.id
  role_definition_name = each.value.role
  principal_id         = local.team_object_ids[each.value.member]
  # Skips the directory lookup that fails right after an invitation (replication delay).
  principal_type = "User"

  lifecycle {
    precondition {
      condition     = local.team_object_ids[each.value.member] != data.azurerm_client_config.current.object_id
      error_message = "team_members.${each.value.member} is you - remove it, `destroy` would take away your own Owner role."
    }
  }
}

# Key Vault uses RBAC, so Owner alone can't read or write secrets. Subscription scope, so it also
# covers vaults that ../ recreates.
resource "azurerm_role_assignment" "key_vault_secrets" {
  for_each = local.everyone

  scope                = data.azurerm_subscription.current.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = each.value
  principal_type       = "User"
}

# --- Shared state of ../ -----------------------------------------------------------------------------

resource "azurerm_resource_group" "tfstate" {
  name     = "rg-${var.project}-tfstate"
  location = var.location
  tags = {
    project    = var.project
    managed-by = "opentofu"
  }
}

resource "azurerm_storage_account" "tfstate" {
  name                            = "st${var.project}tf${random_string.suffix.result}"
  resource_group_name             = azurerm_resource_group.tfstate.name
  location                        = azurerm_resource_group.tfstate.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  # Entra ID only: access to the state (which contains secrets) follows the role assignments below.
  shared_access_key_enabled = false
  tags                      = azurerm_resource_group.tfstate.tags

  # A broken apply or a bad `state rm` can be undone from an earlier blob version.
  blob_properties {
    versioning_enabled = true

    delete_retention_policy {
      days = 7
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_storage_container" "tfstate" {
  name               = "tfstate"
  storage_account_id = azurerm_storage_account.tfstate.id
}

resource "azurerm_role_assignment" "tfstate" {
  for_each = local.everyone

  scope                = azurerm_storage_account.tfstate.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = each.value
  principal_type       = "User"
}
