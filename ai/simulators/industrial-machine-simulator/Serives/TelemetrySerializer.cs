using System.Text.Json;
using System.Text.Json.Serialization;
using Symulator.Models;

namespace Symulator.Serives
{
    public class TelemetrySerializer
    {
        private readonly JsonSerializerOptions options = new()
        {
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
            WriteIndented = false,
            DefaultIgnoreCondition = JsonIgnoreCondition.Never
        };

        public string Serialize(TelemetryMessage message)
        {
            return JsonSerializer.Serialize(message, options);
        }
    }
}