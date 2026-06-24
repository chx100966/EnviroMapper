using EnviroMapper.Core.Entities;

namespace EnviroMapper.Core.Interfaces;

public interface ISensorReadingRepository
{
    Task<IEnumerable<SensorReading>> GetByDeviceAsync(Guid deviceId, DateTime from, DateTime to, CancellationToken ct = default);
    Task AddAsync(SensorReading reading, CancellationToken ct = default);
    Task AddRangeAsync(IEnumerable<SensorReading> readings, CancellationToken ct = default);
}
