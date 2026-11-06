# Offline like ../tests: every provider is mocked. Plan only - the state account has prevent_destroy.

mock_provider "azurerm" {
  mock_data "azurerm_client_config" {
    defaults = {
      tenant_id = "00000000-0000-0000-0000-000000000001"
      object_id = "00000000-0000-0000-0000-000000000002"
    }
  }

  mock_data "azurerm_subscription" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000"
    }
  }

  mock_resource "azurerm_storage_account" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.Storage/storageAccounts/sttest"
    }
  }
}

mock_provider "azuread" {
  mock_data "azuread_user" {
    defaults = {
      object_id = "00000000-0000-0000-0000-00000000000a"
    }
  }

  mock_resource "azuread_invitation" {
    defaults = {
      user_id = "00000000-0000-0000-0000-00000000000b"
    }
  }
}

mock_provider "random" {}

variables {
  team_members = {
    alice = { email = "alice@student.example.edu" }
    bob   = { email = "bob@example.com", invite = true, roles = ["Contributor", "Reader"] }
  }
}

run "team_gets_roles_and_state_access" {
  command = plan

  assert {
    condition     = length(azuread_invitation.team) == 1 && length(data.azuread_user.team) == 1
    error_message = "Only members with invite = true should be invited, the rest looked up."
  }

  assert {
    condition     = toset(keys(azurerm_role_assignment.team)) == toset(["alice/Owner", "bob/Contributor", "bob/Reader"])
    error_message = "Every member should get each of their roles, Owner by default."
  }

  assert {
    condition     = toset(keys(azurerm_role_assignment.tfstate)) == toset(["alice", "bob", "deployer"])
    error_message = "The team and the deployer all need access to the shared state."
  }

  assert {
    condition     = !azurerm_storage_account.tfstate.shared_access_key_enabled
    error_message = "The state account holds secrets and must be Entra ID only."
  }
}

run "rejects_yourself_as_team_member" {
  command = plan

  variables {
    team_members = {
      me = { email = "me@student.example.edu" }
    }
  }

  override_data {
    target = data.azuread_user.team["me"]
    values = {
      object_id = "00000000-0000-0000-0000-000000000002"
    }
  }

  expect_failures = [azurerm_role_assignment.team]
}
