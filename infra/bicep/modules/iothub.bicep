@description('IoT Hub resource name')
param name string

param location string

resource iotHub 'Microsoft.Devices/IotHubs@2023-06-30' = {
  name: name
  location: location
  sku: {
    name: 'F1'
    capacity: 1
  }
  properties: {}
}

output iotHubConnectionString string = 'HostName=${iotHub.properties.hostName};SharedAccessKeyName=iothubowner'
