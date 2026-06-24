@description('Environment name (dev / staging / prod)')
param environmentName string = 'dev'

@description('Azure region')
param location string = resourceGroup().location

var prefix = 'enviromapper-${environmentName}'

module iotHub 'modules/iothub.bicep' = {
  name: 'iotHubDeploy'
  params: {
    name: '${prefix}-iothub'
    location: location
  }
}

module sql 'modules/sql.bicep' = {
  name: 'sqlDeploy'
  params: {
    serverName: '${prefix}-sql'
    location: location
  }
}
