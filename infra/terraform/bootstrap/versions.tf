terraform {
  required_version = ">= 1.11.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.9"
    }
    # Looks up / invites team members in Microsoft Entra ID.
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.10"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.9"
    }
  }

  # Local state on purpose: this configuration creates the storage account that holds the state of
  # ../ (chicken and egg). Its state has no secrets, and whoever runs it is the subscription Owner.
}
