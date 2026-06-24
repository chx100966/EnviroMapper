using EnviroMapper.Core.Interfaces;
using Microsoft.AspNetCore.Mvc;

namespace EnviroMapper.API.Controllers;

[ApiController]
[Route("api/[controller]")]
public class DevicesController(IDeviceRepository devices) : ControllerBase
{
    [HttpGet]
    public async Task<IActionResult> GetAll(CancellationToken ct)
        => Ok(await devices.GetAllAsync(ct));

    [HttpGet("{id:guid}")]
    public async Task<IActionResult> GetById(Guid id, CancellationToken ct)
    {
        var device = await devices.GetByIdAsync(id, ct);
        return device is null ? NotFound() : Ok(device);
    }
}
