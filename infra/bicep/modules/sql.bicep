@description('Azure SQL logical server name')
param serverName string

param location string

@secure()
param adminPassword string = newGuid()

resource sqlServer 'Microsoft.Sql/servers@2023-05-01-preview' = {
  name: serverName
  location: location
  properties: {
    administratorLogin: 'enviromapper-admin'
    administratorLoginPassword: adminPassword
  }
}

resource database 'Microsoft.Sql/servers/databases@2023-05-01-preview' = {
  parent: sqlServer
  name: 'EnviroMapper'
  location: location
  sku: {
    name: 'Basic'
    tier: 'Basic'
  }
}
