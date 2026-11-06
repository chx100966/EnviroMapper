#!/usr/bin/env bash
# Creates or updates one symmetric-key enrollment group in DPS. `tofu apply` runs it for every entry
# of dps_enrollment_groups (dps.tf); it also works by hand with these variables set:
#
#   DPS_CONNECTION_STRING  connection string of a DPS policy with EnrollmentRead + EnrollmentWrite
#   ENROLLMENT_ID          group ID, e.g. agriculture
#   PRIMARY_KEY            base64 group key
#   TWIN_TAGS              JSON tags every device of the group starts with, e.g. {"mode":"agriculture"}
set -euo pipefail

: "${DPS_CONNECTION_STRING:?}" "${ENROLLMENT_ID:?}" "${PRIMARY_KEY:?}" "${TWIN_TAGS:?}"

if ! command -v az >/dev/null; then
  echo "The Azure CLI (az) is required - install it, or set dps_manage_enrollment_groups = false and create the groups by hand (README.md)." >&2
  exit 1
fi

if ! az extension show --name azure-iot --output none 2>/dev/null; then
  az extension add --name azure-iot --only-show-errors
fi

common=(
  --login "$DPS_CONNECTION_STRING"
  --enrollment-id "$ENROLLMENT_ID"
  --only-show-errors
)

# --output none: the response contains the group keys.
settings=(
  --primary-key "$PRIMARY_KEY"
  --initial-twin-tags "$TWIN_TAGS"
  --provisioning-status enabled
  --output none
)

if az iot dps enrollment-group show "${common[@]}" --output none 2>/dev/null; then
  az iot dps enrollment-group update "${common[@]}" "${settings[@]}"
  echo "Updated DPS enrollment group $ENROLLMENT_ID"
else
  az iot dps enrollment-group create "${common[@]}" "${settings[@]}"
  echo "Created DPS enrollment group $ENROLLMENT_ID"
fi
