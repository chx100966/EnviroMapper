provider "azurerm" {
  # Subscription comes from ARM_SUBSCRIPTION_ID, like in ../ (see README.md).
  resource_provider_registrations = "none"
  resource_providers_to_register  = ["Microsoft.Storage"]

  # The state container is managed over ARM, and nobody needs account keys for the state blobs.
  storage_use_azuread = true

  features {}
}

# Tenant comes from the Azure CLI login (the subscription's directory).
provider "azuread" {}
