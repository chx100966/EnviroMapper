using EnviroMapper.Core.Entities;

namespace EnviroMapper.Core.Interfaces;

public interface IDeviceRepository
{
    Task<IEnumerable<Device>> GetAllAsync(CancellationToken ct = default);
    Task<Device?> GetByIdAsync(Guid id, CancellationToken ct = default);
    Task AddAsync(Device device, CancellationToken ct = default);
    Task UpdateAsync(Device device, CancellationToken ct = default);
    Task DeleteAsync(Guid id, CancellationToken ct = default);
}
