output "backend_config" {
  description = "Contents of ../backend.hcl - commit it, then everyone runs `tofu init -backend-config=backend.hcl` in ../."
  value       = <<-EOT
    resource_group_name  = "${azurerm_resource_group.tfstate.name}"
    storage_account_name = "${azurerm_storage_account.tfstate.name}"
    container_name       = "${azurerm_storage_container.tfstate.name}"
    key                  = "dev.tfstate"
    use_azuread_auth     = true
  EOT
}

output "team_object_ids" {
  description = "Entra ID object IDs of the team members."
  value       = local.team_object_ids
}

output "pending_invitations" {
  description = "Redeem links for guests, in case the invitation email lands in spam."
  value       = { for key, inv in azuread_invitation.team : key => inv.redeem_url }
  sensitive   = true
}
