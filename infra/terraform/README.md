# EnviroMapper — Azure infrastructure (OpenTofu)

Everything the system needs in Azure, sized for an engineering thesis: one environment, used a few
hours at a time, no production load. Every component is either free-tier or scale-to-zero, so
**nothing has to be stopped between sessions** — an idle environment costs close to $0.

```
 devices / ai/simulators ──MQTT/AMQP──▶ IoT Hub (F1)
                                           │ built-in endpoint, consumer group "functions"
                                           ▼
                              Function App (Flex Consumption, Python)
                              validation + anomaly detection ──▶ Azure SQL (free offer, serverless)
                                                                          ▲
 browser ──▶ Static Web App (React SPA) ──HTTPS──▶ App Service F1 (.NET API)

 Key Vault (secrets, read via managed identities) · Storage (function host, models)
 Log Analytics + Application Insights (capped)    · Budget alert on the resource group
```

## Resources and estimated cost

| Component | Resource / SKU | Free limit that matters | Cost / month |
|---|---|---|---|
| Device ingestion | IoT Hub **F1** | 8,000 messages/day (0.5 KB each), 500 devices, one F1 hub per subscription | $0 |
| Telemetry processing | Functions **Flex Consumption**, 512 MB, max 2 instances | 100,000 GB-s + 250,000 executions/month | $0 (≈ $1 if the grant doesn't apply, see below) |
| Database | Azure SQL **free offer**, serverless `GP_S_Gen5_1` (0.5–1 vCore), 32 GB | 100,000 vCore-seconds/month ≈ 30–40 h online | $0 (pauses when used up) |
| Backend API | App Service **F1** Linux | 60 CPU-minutes/day, 1 GB RAM, 165 MB outbound/day | $0 |
| Frontend | Static Web Apps **Free** (or Storage static website) | 100 GB bandwidth/month | $0 |
| Secrets | Key Vault Standard | — | < $0.01 |
| Function host, models | Storage account, Standard LRS | — | $0.05–1 (mostly trigger checkpoint writes) |
| Logs, APM | Log Analytics + Application Insights, capped at 0.1 GB/day | 5 GB/month | $0 |
| Cost guard | Budget on the resource group (optional) | — | $0 |
| **Total** | | | **≈ $0–2** |

List prices for Poland Central in USD (Azure Retail Prices API, October 2026). The $100 Azure for
Students credit covers the whole thesis with a wide margin.

**Assumed usage:** one `dev` environment; the cloud is used a few hours a day on ~15 days a month;
the simulator runs 3 devices (one per mode), each sending one message every 15 s with all readings
of that tick; a handful of users (the team and the supervisor).

### Where the free limits bite

- **IoT Hub, 8,000 messages/day** (resets 00:00 UTC; when it's used up the hub rejects device
  messages). 3 devices × 1 message / 15 s = 720 messages/h, i.e. ~11 h of simulation per day.
  `ai/simulators/run_simulator.py` currently emits every sensor reading separately — sending them
  as one message per tick is 3× cheaper.
- **SQL, 100,000 vCore-seconds/month.** While online the database is billed at least 0.67 vCore,
  so it lasts ~41 h idle-online or ~28 h under load, and every wake-up costs at least the 15-minute
  auto-pause delay. Anything holding a connection keeps it awake: SSMS/Azure Data Studio Object
  Explorer, connection pools, health checks. Use a local SQL Server in Docker for day-to-day
  development and the Azure database for integration tests and demos. Track the
  *Free amount remaining* metric on the database. When the allowance is gone the database stays
  paused until the 1st of the next month; switching it to *continue with charges* is irreversible
  (then $0.57 per vCore-hour).
- **App Service F1:** over the CPU or bandwidth quota the API returns 403 until midnight UTC;
  after ~20 idle minutes the app unloads and the next request has a cold start. No Always On, so
  background workers don't belong in the API — telemetry is read by the Function App.
- **Functions free grant** "applies to paid subscriptions only"; on a credit offer such as Azure for
  Students assume you pay for it: at 512 MB and ≥ 1 s billed per execution, 50,000 executions/month
  ≈ 25,000 GB-s ≈ $0.95.

### Upgrade path

| When | Change | List price |
|---|---|---|
| More than 8,000 messages/day, 24/7 simulation | New IoT Hub B1 (400,000 msgs/day, no cloud-to-device/twins) or S1 — F1 can't be upgraded in place | $10 / $25 per month |
| API always on, no CPU quota | App Service B1 Linux | ≈ $13 per month |
| Database online all the time | SQL Database Basic (5 DTU, 2 GB) | ≈ $4.90 per month |

## Before the first apply

You need [OpenTofu](https://opentofu.org/docs/intro/install/) ≥ 1.11 (CI uses 1.13.2), the Azure
CLI, and the **Owner** role on the subscription — OpenTofu creates role assignments and registers
resource providers. The configuration is plain HCL, so the directory is still called `terraform/`
and the variables file `terraform.tfvars`.

Azure for Students subscriptions may only deploy to ~5 regions (different for each person) and
often can't create Static Web Apps at all. Check before the first apply:

```bash
az login
az account set --subscription "<subscription name or id>"

# Look for the "Allowed resource deployment regions" assignment and its list of locations
az policy assignment list --query "[].{name:displayName, parameters:parameters}" -o jsonc

# Flex Consumption isn't available in every region
az functionapp list-flexconsumption-locations --query "[].name" -o tsv
```

Choose a `location` that is in both lists. If creating the Static Web App fails with
`RequestDisallowedByAzure`, set `frontend_hosting = "storage"`.

## Usage

```bash
cd infra/terraform
export ARM_SUBSCRIPTION_ID=$(az account show --query id -o tsv)
cp terraform.tfvars.example terraform.tfvars   # optional overrides, git-ignored

tofu init
tofu plan -out=tfplan
tofu apply tfplan
tofu output
```

The first apply takes several minutes (the SQL server and IoT Hub are the slow ones), including a
deliberate 60 s wait for Key Vault permissions to propagate.

`tofu test` needs no Azure login: it applies the configuration against mocked providers and
fails if a paid tier slips in (CI runs it together with `tofu validate`, for both this directory
and `bootstrap/`, on every PR; `tofu init -backend=false` is enough for that). Changing
a SKU on purpose means updating [tests/free_tier.tftest.hcl](tests/free_tier.tftest.hcl) and the
cost table above.

Secrets (SQL password, IoT Hub keys, JWT signing key) are generated by OpenTofu, stored in Key
Vault and read by the apps through Key Vault references — never commit them anywhere. They are also
in the state, which is why `*.tfstate` and `terraform.tfvars` are git-ignored.

### After the first apply

- **Simulator devices:** `az extension add --name azure-iot`, then
  `az iot hub device-identity create --hub-name "$(tofu output -raw iothub_name)" --device-id sim-agriculture-01`
  and `az iot hub device-identity connection-string show` with the same arguments. Keep the device
  connection string in `ai/.env`.
- **Frontend deploys:** `tofu output -raw static_web_app_deployment_token` goes into the
  GitHub secret used by the Static Web Apps deploy action.
- **Code deploys** (`az webapp deploy`, `func azure functionapp publish`) aren't part of this
  skeleton yet.
- If the API shows raw `@Microsoft.KeyVault(...)` values right after the first apply, restart it
  once (`az webapp restart`): its access to Key Vault is granted only after the app exists.

## Remote state (when more than one person runs OpenTofu)

State is local by default, so only one person can run `apply`. To share it, create a small storage
account outside this configuration (costs cents), uncomment `backend "azurerm" {}` in
[versions.tf](versions.tf) and migrate:

```bash
az group create --name rg-enviromapper-tfstate --location polandcentral
az storage account create --name <unique-name> --resource-group rg-enviromapper-tfstate \
  --sku Standard_LRS --min-tls-version TLS1_2 --allow-blob-public-access false
az storage container create --name tfstate --account-name <unique-name> --auth-mode login

tofu init -migrate-state \
  -backend-config="resource_group_name=rg-enviromapper-tfstate" \
  -backend-config="storage_account_name=<unique-name>" \
  -backend-config="container_name=tfstate" \
  -backend-config="key=dev.tfstate" \
  -backend-config="use_azuread_auth=true"
```

Everyone who runs OpenTofu then needs *Storage Blob Data Contributor* on that account. The state
contains secrets, so treat access to it like access to Key Vault.

## Tear down

`tofu destroy` removes everything, including the Key Vault (purge protection is off on
purpose), and frees the subscription's F1 IoT Hub slot. A free-offer SQL database slot can take up
to an hour to become available again.

## Design decisions

- **azurerm + azapi:** azurerm 5.9 can't enable the SQL free offer (`useFreeLimit`), and the offer
  can only be chosen when the database is created, so that one resource uses azapi.
- **Flex Consumption** instead of the Linux Consumption plan, which retires on 2028-09-30.
- **Serverless SQL with auto-pause** costs nothing while idle; the price is a resume delay of up to
  a minute, which clients absorb with retry logic (EF Core `EnableRetryOnFailure`).
- **Managed identities + Key Vault references** for app secrets. Exception: the Function App host
  storage uses the account key, because azurerm writes an invalid `AzureWebJobsStorage` value for
  identity-based storage on Flex Consumption.
- **Public endpoints with firewall rules** instead of private networking: private endpoints and VNet
  integration need paid plans and would cost more than the rest of the system.
- **.NET 8** for the API matches the current code, but its support ends on 2026-11-10 — move to
  .NET 10 together with the code (`api_dotnet_version = "10.0"`).

Not covered yet: CI/CD deployments to Azure, Entra ID (passwordless) access from the apps to SQL,
alerts on the IoT Hub daily quota and the SQL free allowance.
