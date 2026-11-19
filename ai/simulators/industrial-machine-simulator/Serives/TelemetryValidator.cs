using System;
using System.IO;
using System.Text.Json;
using Json.Schema;

namespace Symulator.Serives
{
    public class TelemetryValidator
    {
        private readonly JsonSchema schema;

        public TelemetryValidator()
        {
            string schemaPath = Path.Combine(
                AppContext.BaseDirectory,
                "Schemas",
                "v1.schema.json"
            );

            if (!File.Exists(schemaPath))
            {
                throw new FileNotFoundException(
                    "Nie znaleziono pliku v1.schema.json",
                    schemaPath
                );
            }

            schema = JsonSchema.FromFile(schemaPath);
        }

        public bool IsValid(string json)
        {
            using JsonDocument document = JsonDocument.Parse(json);

            var result = schema.Evaluate(document.RootElement);

            return result.IsValid;
        }
    }
}