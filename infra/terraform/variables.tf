variable "project" {
  description = "Short project name used in resource names."
  type        = string
  default     = "enviromapper"

  validation {
    # Part of the storage account name (max 24 lowercase alphanumerics in total).
    condition     = can(regex("^[a-z0-9]{3,12}$", var.project))
    error_message = "project must be 3-12 lowercase letters or digits."
  }
}

variable "environment" {
  description = "Environment name, e.g. dev or demo."
  type        = string
  default     = "dev"

  validation {
    condition     = can(regex("^[a-z0-9]{2,4}$", var.environment))
    error_message = "environment must be 2-4 lowercase letters or digits."
  }
}

variable "location" {
  description = "Region for all regional resources. Azure for Students only allows a few regions per subscription - check the \"Allowed resource deployment regions\" policy assignment first. See README.md."
  type        = string
  default     = "germanywestcentral"
}

variable "tags" {
  description = "Extra tags added to every resource."
  type        = map(string)
  default     = {}
}

# --- Frontend ----------------------------------------------------------------

variable "frontend_hosting" {
  description = "How the React SPA is hosted: \"static_web_app\" (Static Web Apps Free) or \"storage\" (Storage static website - fallback when Static Web Apps is blocked, which happens on Azure for Students). Storage by default: Static Web Apps only exists in regions our subscription doesn't allow."
  type        = string
  default     = "storage"

  validation {
    condition     = contains(["static_web_app", "storage"], var.frontend_hosting)
    error_message = "frontend_hosting must be \"static_web_app\" or \"storage\"."
  }
}

variable "static_web_app_location" {
  description = "Region of the Static Web App resource (metadata only, content is served globally). Static Web Apps exists only in westus2, centralus, eastus2, westeurope and eastasia."
  type        = string
  default     = "westeurope"
}

# --- Backend API (App Service) -------------------------------------------------

variable "api_dotnet_version" {
  description = "Runtime of the backend API. Matches backend/*.csproj; .NET 8 support ends on 2026-11-10, move to \"10.0\" together with the code."
  type        = string
  default     = "8.0"
}

# --- Cost guards ----------------------------------------------------------------

variable "log_daily_quota_gb" {
  description = "Daily ingestion cap for Log Analytics and Application Insights. 0.1 GB/day stays well below the 5 GB/month free allowance."
  type        = number
  default     = 0.1
}

variable "budget_amount" {
  description = "Monthly budget for the resource group, in the subscription's billing currency (USD on Azure for Students)."
  type        = number
  default     = 10
}

variable "budget_contact_emails" {
  description = "Who gets budget alerts (50%/100% actual, 100% forecast). Empty list = no budget is created."
  type        = list(string)
  default     = []
}
