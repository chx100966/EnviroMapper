terraform {
  required_version = ">= 1.11.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.9"
    }
    # Only for settings azurerm does not expose yet (Azure SQL free offer, see sql.tf).
    azapi = {
      source  = "Azure/azapi"
      version = "~> 2.13"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.9"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.14"
    }
  }

  # Shared state in the storage account created by bootstrap/; the settings are in backend.hcl
  # (`tofu init -backend-config=backend.hcl`). See README.md, "Working as a team".
  backend "azurerm" {}
}
