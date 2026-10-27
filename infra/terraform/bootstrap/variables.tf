variable "project" {
  description = "Short project name used in resource names (same as in ../)."
  type        = string
  default     = "enviromapper"

  validation {
    condition     = can(regex("^[a-z0-9]{3,12}$", var.project))
    error_message = "project must be 3-12 lowercase letters or digits."
  }
}

variable "location" {
  description = "Region of the state storage account. Must be one of the regions the subscription allows (Azure for Students: see ../README.md)."
  type        = string
  default     = "polandcentral"
}

variable "team_members" {
  description = <<-EOT
    Other people who work in this subscription, as key => settings. Don't list yourself: the person
    running this configuration already is the Owner, and their data-plane roles are added anyway.
      email  - school/work address of someone already in the subscription's directory, or any
               address to invite as a guest (invite = true)
      invite - send a guest (B2B) invitation instead of looking up an existing user
      roles  - roles on the whole subscription; Owner lets them run `tofu apply` in ../
  EOT
  type = map(object({
    email  = string
    invite = optional(bool, false)
    roles  = optional(list(string), ["Owner"])
  }))
  default = {}

  validation {
    condition     = alltrue([for m in values(var.team_members) : can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", m.email))])
    error_message = "Every team member needs a valid email address."
  }
}
