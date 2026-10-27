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
  description = "Region for all regional resources. Azure for Students only allows a few regions per subscription - check the \"Allowed resource deployment regions\" policy assignment first. Of the five our subscription allows, only germanywestcentral has IoT Hub (see README.md)."
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

# --- Telemetry processing (Function App, Flex Consumption) ----------------------

variable "function_runtime" {
  description = "Function App stack. Python matches the ai/ module; \"dotnet-isolated\" would let the function reuse EnviroMapper.Core."
  type = object({
    name    = string
    version = string
  })
  default = {
    name    = "python"
    version = "3.11"
  }
}

variable "function_instance_memory_mb" {
  description = "Instance size. Billing is memory x execution time, so 512 MB costs 4x less than the 2048 MB default; raise it only if model inference needs it."
  type        = number
  default     = 512

  validation {
    condition     = contains([512, 2048, 4096], var.function_instance_memory_mb)
    error_message = "function_instance_memory_mb must be 512, 2048 or 4096."
  }
}

variable "function_maximum_instance_count" {
  description = "Scale-out ceiling (cost guard). The IoT Hub free tier has 2 partitions, so the trigger never uses more than 2 instances anyway."
  type        = number
  default     = 2

  validation {
    condition     = var.function_maximum_instance_count >= 1 && var.function_maximum_instance_count <= 1000
    error_message = "function_maximum_instance_count must be between 1 and 1000."
  }
}

# --- Database (Azure SQL free offer) ------------------------------------------

variable "sql_sku_name" {
  description = "Serverless General Purpose SKU (GP_S_Gen5_<max vCores>). The free offer allows up to 4 vCores; a lower ceiling burns the monthly 100,000 vCore-seconds more slowly."
  type        = string
  default     = "GP_S_Gen5_1"

  validation {
    condition     = can(regex("^GP_S_Gen5_[124]$", var.sql_sku_name))
    error_message = "sql_sku_name must be GP_S_Gen5_1, GP_S_Gen5_2 or GP_S_Gen5_4 (free offer limit)."
  }
}

variable "sql_auto_pause_delay_minutes" {
  description = "Idle minutes before the database pauses. Every resume costs at least this much compute, so keep it at the 15-minute minimum."
  type        = number
  default     = 15

  validation {
    condition     = var.sql_auto_pause_delay_minutes >= 15
    error_message = "sql_auto_pause_delay_minutes must be at least 15."
  }
}

variable "sql_firewall_allowed_ips" {
  description = "Public IPv4 addresses allowed to connect to SQL directly (e.g. developer machines), as name => IP."
  type        = map(string)
  default     = {}
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
