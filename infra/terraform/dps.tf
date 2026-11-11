# Device Provisioning Service: a device registers once with a key derived from its mode's enrollment
# group and gets its IoT Hub, device ID and twin tags back - nobody creates devices by hand.
# S1 is the only tier: $0.10 per 1,000 operations (registrations, enrollment changes) - cents.

# What DPS needs to create device identities in the hub (the rights of iothubowner).
resource "azurerm_iothub_shared_access_policy" "dps" {
  name                = "provisioning-service"
  resource_group_name = azurerm_resource_group.main.name
  iothub_name         = azurerm_iothub.main.name

  registry_read   = true
  registry_write  = true
  service_connect = true
  device_connect  = true
}

resource "azurerm_iothub_dps" "main" {
  name                = local.names.dps
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  allocation_policy   = "Hashed" # one linked hub, so every device lands on it

  sku {
    name     = "S1"
    capacity = 1
  }

  linked_hub {
    connection_string = azurerm_iothub_shared_access_policy.dps.primary_connection_string
    location          = azurerm_iothub.main.location
  }

  tags = local.tags
}

# Enrollment management only - narrower than the built-in provisioningserviceowner.
resource "azurerm_iothub_dps_shared_access_policy" "enrollments" {
  name                = "enrollment-manager"
  resource_group_name = azurerm_resource_group.main.name
  iothub_dps_name     = azurerm_iothub_dps.main.name

  enrollment_read  = true
  enrollment_write = true
}

# Symmetric group keys. A device's own key is HMAC-SHA256(group key, registration ID), so the group
# key stays with the team (Key Vault) and every device still has a key of its own. Generated here so
# the groups keep their keys when they are recreated.
resource "random_bytes" "dps_group_key" {
  for_each = toset(var.dps_enrollment_groups)

  length = 64
}

locals {
  dps_enrollment_key_secret_names = { for group in var.dps_enrollment_groups : group => "dps-enrollment-key-${group}" }

  # Stored with the other secrets (keyvault.tf), where the team reads them to derive device keys.
  dps_enrollment_key_secrets = {
    for group, name in local.dps_enrollment_key_secret_names : name => random_bytes.dps_group_key[group].base64
  }
}

# Enrollment groups live in the DPS data plane, which azurerm doesn't manage, so the script creates or
# updates them with the Azure CLI. It signs in with the policy above, not with `az login`.
resource "terraform_data" "dps_enrollment_group" {
  for_each = var.dps_manage_enrollment_groups ? toset(var.dps_enrollment_groups) : toset([])

  triggers_replace = {
    dps       = azurerm_iothub_dps.main.id
    key       = sha256(random_bytes.dps_group_key[each.key].base64)
    twin_tags = jsonencode({ mode = each.key })
  }

  provisioner "local-exec" {
    command = "bash '${path.module}/scripts/dps-enrollment-group.sh'"

    # Environment variables never appear in the output; marking them sensitive would only hide the
    # script's error messages.
    environment = {
      DPS_CONNECTION_STRING = nonsensitive(azurerm_iothub_dps_shared_access_policy.enrollments.primary_connection_string)
      ENROLLMENT_ID         = each.key
      PRIMARY_KEY           = nonsensitive(random_bytes.dps_group_key[each.key].base64)
      TWIN_TAGS             = jsonencode({ mode = each.key })
    }
  }
}

# Telemetry arrives with its mode as an application property, taken from the twin tag set by the
# enrollment group, so the Function App needs neither the body nor a twin lookup to know it. Devices
# created by hand without the tag get the literal string "$twin.tags.mode". F1 allows 2 enrichments.
resource "azurerm_iothub_enrichment" "mode" {
  key                 = "mode"
  value               = "$twin.tags.mode"
  resource_group_name = azurerm_resource_group.main.name
  iothub_name         = azurerm_iothub.main.name
  endpoint_names      = ["events"]
}
