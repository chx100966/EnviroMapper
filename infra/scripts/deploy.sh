#!/usr/bin/env bash
set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-enviromapper-rg}"
LOCATION="${LOCATION:-polandcentral}"
ENV="${ENV:-dev}"

echo "Deploying EnviroMapper to resource group: $RESOURCE_GROUP (env=$ENV)"

az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none

az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file "$(dirname "$0")/../bicep/main.bicep" \
  --parameters environmentName="$ENV" location="$LOCATION"

echo "Deployment complete."
