namespace EnviroMapper.Core.Entities;

public class Device
{
    public Guid Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public DeviceMode Mode { get; set; }
    public string Location { get; set; } = string.Empty;
    public bool IsActive { get; set; }
    public DateTime RegisteredAt { get; set; }
    public ICollection<SensorReading> Readings { get; set; } = [];
}

public enum DeviceMode
{
    Agriculture,
    Industry,
    Weather
}
