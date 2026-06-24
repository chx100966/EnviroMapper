export type DeviceMode = 'Agriculture' | 'Industry' | 'Weather'

export interface Device {
  id: string
  name: string
  mode: DeviceMode
  location: string
  isActive: boolean
  registeredAt: string
}

export interface SensorReading {
  id: number
  deviceId: string
  sensorType: string
  value: number
  unit: string
  timestamp: string
  isAnomaly: boolean
}
