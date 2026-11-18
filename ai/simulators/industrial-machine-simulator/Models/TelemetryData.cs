using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Symulator.Models
{
    public class TelemetryData
    {
        public DateTime Timestamp { get; set; }
        public double Temperature { get; set; }
        public double Pressure { get; set; }
        public double Vibration { get; set; }
        public int Rpm { get; set; }
        public double Current {  get; set; }
        public double Load {  get; set; }
        public string MachineStatus { get; set; } = "Zatrzymana";

    }
}
