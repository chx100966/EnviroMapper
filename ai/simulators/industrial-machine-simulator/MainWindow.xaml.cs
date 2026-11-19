using Symulator.Models;
using Symulator.Serives;
using System.Text;
using System.Timers;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Documents;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Navigation;
using System.Windows.Shapes;
using System.Windows.Threading;


namespace Symulator
{
    /// <summary>
    /// Interaction logic for MainWindow.xaml
    /// </summary>
    public partial class MainWindow : Window
    {
        private readonly MachineSimulator simulator;
        private readonly DispatcherTimer timer;
        private readonly TelemetrySerializer serializer;
        private readonly TelemetryValidator validator;
        public MainWindow()
        {
            InitializeComponent();
            simulator = new MachineSimulator();
            serializer = new TelemetrySerializer();
            validator = new TelemetryValidator();

            timer = new DispatcherTimer();
            timer.Interval = TimeSpan.FromSeconds(1);
            timer.Tick += Timer_Tick;
            timer.Start();

            UpdateInterface(simulator.CurrentData);
        }
        private void StartButton_Click(object sender, RoutedEventArgs e)
        {
            simulator.Start();

            UpdateInterface(simulator.CurrentData);
        }

        private void StopButton_Click(object sender, RoutedEventArgs e)
        {
            simulator.Stop();

            UpdateInterface(simulator.CurrentData);
        }

        private void Timer_Tick(object? sender, EventArgs e)
        {
            TelemetryData data = simulator.Update();

            UpdateInterface(data);

            if (simulator.IsRunning)
            {
                TelemetryMessage message = simulator.CreateTelemetryMessage();

                string json = serializer.Serialize(message);

                bool isValid = validator.IsValid(json);

                if (isValid)
                {
                    System.Diagnostics.Debug.WriteLine("[OK] Wiadomość JSON poprawna:");
                }
                else
                {
                    System.Diagnostics.Debug.WriteLine("[BŁĄD] Wiadomość JSON niezgodna ze schematem!");
                }

                System.Diagnostics.Debug.WriteLine(json);
            }
        }

        private void SetColor(System.Windows.Controls.TextBlock element, double value, double min, double max)
        {
            if (simulator.IsRunning == true)
            {
                if (value >= min && value <= max)
                {
                    element.Foreground = System.Windows.Media.Brushes.Green;
                }
                else
                {
                    element.Foreground = System.Windows.Media.Brushes.Red;
                }
            }
            else
            {
                element.Foreground = System.Windows.Media.Brushes.Black;
            }
        }
        private void UpdateInterface(TelemetryData data)
        {
            TemperatureValue.Text = $"{data.Temperature:F1} °C";
            PressureValue.Text = $"{data.Pressure:F2} bar";
            VibrationValue.Text = $"{data.Vibration:F2} mm/s";
            RpmValue.Text = $"{data.Rpm} RPM";
            CurrentValue.Text = $"{data.Current:F2} A";
            LoadValue.Text = $"{data.Load:F1} %";

            MachineStatus.Text = data.MachineStatus;

            SetColor(TemperatureValue, data.Temperature, 20, 60);
            SetColor(PressureValue, data.Pressure, 5, 7);
            SetColor(VibrationValue, data.Vibration, 0, 2);
            SetColor(RpmValue, data.Rpm, 1400, 1600);
            SetColor(CurrentValue, data.Current, 0, 6);
            SetColor(LoadValue, data.Load, 0, 80);


            MachineStatus.Text = data.MachineStatus;
            if (data.MachineStatus == "PRACUJE")
            {
                MachineStatus.Foreground = new System.Windows.Media.SolidColorBrush(System.Windows.Media.Colors.Green);
            }
            else 
            {
                MachineStatus.Foreground = new System.Windows.Media.SolidColorBrush(System.Windows.Media.Colors.Red);
            }

        }

        private void ScenarioButton_Click(object sender, RoutedEventArgs e)
        {
            if (Chose.SelectedItem is ComboBoxItem selectedItem)
            {
                string scenario = selectedItem.Content.ToString()!;
                simulator.SetScenario(scenario);

                MessageBox.Show(
                    $"Zastosowano scenariusz: {scenario}",
                    "Symulator");
            }
        }

    }
}