using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Text.Json.Serialization;
using System.Threading.Tasks;

namespace Symulator.Models
{
    public class TelemetryMessage
    {
        [JsonPropertyName("schemaVersion")]
        public int SchemaVersion { get; set; } = 1;

        [JsonPropertyName("messageId")]
        public string MessageId { get; set; } = Guid.NewGuid().ToString();

        [JsonPropertyName("deviceId")]
        public string DeviceId { get; set; } = "sim-industry-01";

        [JsonPropertyName("mode")]
        public string Mode { get; set; } = "industry";

        [JsonPropertyName("timestamp")]
        public string Timestamp { get; set; } = "";

        [JsonPropertyName("readings")]
        public IndustryReadings Readings { get; set; } = new();
    }

    public class IndustryReadings
    {
        [JsonPropertyName("vibration")]
        public double Vibration { get; set; }

        [JsonPropertyName("temperature")]
        public double Temperature { get; set; }

        [JsonPropertyName("pressure")]
        public double Pressure { get; set; }
    }
}
