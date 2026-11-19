using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Symulator.Models;

namespace Symulator.Serives
{
    public class MachineSimulator
    {
        private readonly Random random = new Random();
        private string currentScenario = "Normalna praca";
        public bool IsRunning { get; private set; }
        public TelemetryData CurrentData { get; private set; } = new TelemetryData();
        public MachineSimulator() 
        {
            ResetValues();
        }
        public void Start()
        {
            IsRunning = true;
            CurrentData.MachineStatus = "PRACUJE";
        }
        public void Stop()
        {
            IsRunning = false;
            CurrentData.MachineStatus = "ZATRZYMANA";
            CurrentData.Rpm = 0;
            CurrentData.Current = 0;
            CurrentData.Load = 0;
        }
        private void ResetValues()
        {
            CurrentData = new TelemetryData
            {
                Timestamp = DateTime.Now,
                Temperature = 22,
                Pressure = 2.0,
                Vibration = 0,
                Rpm = 0,
                Current = 0,
                Load = 0,
                MachineStatus = "ZATRZYMANA"
            };
        }
        private double MoveTowards(double current, double target, double maxDelta)
        {
            if (Math.Abs(target - current) <= maxDelta)
                return target;

            return current + Math.Sign(target - current) * maxDelta;
        }
        public void SetScenario(string scenario)
        {
            currentScenario = scenario;
        }
        public TelemetryData Update()
        {
            if (IsRunning)
            {
                switch (currentScenario)
                {
                    case "Normalna praca":

                        CurrentData.Temperature = MoveTowards(
                            CurrentData.Temperature, 40, 0.2)
                            + RandomChange(-0.2, 0.2);

                        CurrentData.Pressure = MoveTowards(
                            CurrentData.Pressure, 6.0, 0.05)
                            + RandomChange(-0.03, 0.03);

                        CurrentData.Vibration = MoveTowards(
                            CurrentData.Vibration, 0.8, 0.03)
                            + RandomChange(-0.03, 0.03);

                        CurrentData.Load = MoveTowards(
                            CurrentData.Load, 45, 1.0)
                            + RandomChange(-0.5, 0.5);

                        CurrentData.Rpm = random.Next(1450, 1551);

                        break;

                    case "Przegrzewanie":

                        CurrentData.Temperature += RandomChange(0.2, 0.5);

                        CurrentData.Pressure += RandomChange(-0.03, 0.03);

                        CurrentData.Vibration += RandomChange(-0.02, 0.02);

                        CurrentData.Load += RandomChange(-0.5, 0.5);

                        CurrentData.Rpm = random.Next(1450, 1551);

                        break;

                    case "Spadek ciśnienia":

                        CurrentData.Pressure -= RandomChange(0.03, 0.08);

                        CurrentData.Temperature += RandomChange(-0.05, 0.1);

                        CurrentData.Vibration += RandomChange(-0.02, 0.02);

                        CurrentData.Load += RandomChange(-0.5, 0.5);

                        CurrentData.Rpm = random.Next(1450, 1551);

                        break;

                    case "Uszkodzenie łożyska":

                        CurrentData.Vibration += RandomChange(0.03, 0.08);

                        CurrentData.Temperature += RandomChange(0.05, 0.15);

                        CurrentData.Pressure += RandomChange(-0.02, 0.02);

                        CurrentData.Load += RandomChange(-0.5, 0.5);

                        CurrentData.Rpm = random.Next(1400, 1501);

                        break;

                    case "Przeciążenie":

                        CurrentData.Load += RandomChange(0.5, 1.5);

                        CurrentData.Temperature += RandomChange(0.1, 0.3);

                        CurrentData.Vibration += RandomChange(0.02, 0.05);

                        CurrentData.Pressure += RandomChange(-0.02, 0.02);

                        CurrentData.Rpm = random.Next(1300, 1451);

                        break;
                }

                CurrentData.Temperature = Math.Clamp(CurrentData.Temperature, 0, 150);
                CurrentData.Pressure = Math.Clamp(CurrentData.Pressure, 0, 10);
                CurrentData.Vibration = Math.Clamp(CurrentData.Vibration, 0, 15);
                CurrentData.Load = Math.Clamp(CurrentData.Load, 0, 150);

                CurrentData.Current = 2.0
                    + (CurrentData.Load * 0.08)
                    + RandomChange(-0.2, 0.2);
            }

            CurrentData.Timestamp = DateTime.Now;

            return CurrentData;
        }

        private double RandomChange(double min, double max)
        {
            return random.NextDouble() * (max - min) + min;
        }
        public TelemetryMessage CreateTelemetryMessage()
        {
            return new TelemetryMessage
            {
                MessageId = Guid.NewGuid().ToString().ToLowerInvariant(),
                DeviceId = "sim-industry-01",
                Mode = "industry",
                Timestamp = DateTime.UtcNow.ToString(
                "yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",
                System.Globalization.CultureInfo.InvariantCulture
                ),
                Readings = new IndustryReadings
                {
                    Vibration = CurrentData.Vibration,
                    Temperature = CurrentData.Temperature,
                    Pressure = CurrentData.Pressure
                }
            };
        }
    }
}
