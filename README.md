# Week 7 Project: CBS Dutch Housing Purchase Prices Pipeline

## What it does

This project is a data engineering pipeline for Dutch housing purchase price data from the CBS Open Data API.

The pipeline fetches CBS housing records, validates them with Pydantic, transforms them with pandas, stores transformed rows in Azure Postgres, and uploads the raw API response to Azure Blob Storage.

## Data source

CBS Open Data API:

```text
https://opendata.cbs.nl/ODataApi/odata/85792ENG/TypedDataSet
```

## Architecture

```text
CBS OData API ──► pipeline.py ──► Pydantic validation ──► pandas transformation (rename CBS technical columns, parse period_year, parse period_type, parse period_quarter, convert numeric columns) ──► Azure Postgres (schema: dev_pavel_tisner, table: cbs_housing_purchase_prices) ──► Azure Blob Storage (container: raw, prefix: cbs_housing)
```

## Run locally

Create `.env` from `.env.example` and fill it with your own values from Azure Key Vault.

My local `.env` uses exported variables:

```bash
export API_URL="https://opendata.cbs.nl/ODataApi/odata/85792ENG/TypedDataSet"
export POSTGRES_URL="$(az keyvault secret show --vault-name kv-hyf-data --name postgres-url --query value -o tsv)"
export AZURE_STORAGE_CONNECTION_STRING="$(az keyvault secret show --vault-name kv-hyf-data --name storage-connection-string --query value -o tsv)"
export DB_SCHEMA="dev_pavel_tisner"
export BLOB_CONTAINER="raw"
export BLOB_PREFIX="cbs_housing"
export LOG_LEVEL="INFO"
```

The Azure Storage connection string must be wrapped in quotes because it contains semicolons.

Load environment variables:

```bash
source .env
```

# Install dependencies
```bash
uv sync
```

# Run directly (without Docker)
```bash
uv run python -m src.pipeline
```

# Or build and run with Docker
```bash
docker build --platform linux/amd64 \
  -t hyfregistry.azurecr.io/cbs-housing-pipeline:latest .

docker run --env-file .env.docker \
  hyfregistry.azurecr.io/cbs-housing-pipeline:latest
```

## Run tests and linting:

```bash
uv run ruff check src/ tests/
uv run pytest tests/ -v
```

## Deploy to Azure

Build for `linux/amd64` and push to Azure Container Registry:

```bash
docker build --platform linux/amd64 \
  -t hyfregistry.azurecr.io/cbs-housing-pipeline:latest .

docker push hyfregistry.azurecr.io/cbs-housing-pipeline:latest
```

Create Container App Job (runs daily at 06:00 UTC):

```bash
az containerapp job create \
  --name cbs-housing-pavel \
  --resource-group rg-hyf-data \
  --environment env-hyf-data \
  --image hyfregistry.azurecr.io/cbs-housing-pipeline:latest \
  --registry-server hyfregistry.azurecr.io \
  --trigger-type Schedule \
  --cron-expression "0 6 * * *" \
  --replica-timeout 300 \
  --replica-retry-limit 1 \
  --cpu 0.5 \
  --memory 1Gi
```

The job uses Azure Container App secrets for sensitive values. The Azure Storage connection string is base64-encoded before being stored as a secret because the original connection string contains semicolons.

```bash
source .env

STORAGE_CONNECTION_STRING_B64=$(printf "%s" "$AZURE_STORAGE_CONNECTION_STRING" | base64 | tr -d '\n')

az containerapp job secret set \
  --name cbs-housing-pavel \
  --resource-group rg-hyf-data \
  --secrets \
    postgres-url="$POSTGRES_URL" \
    storage-connection-string-b64="$STORAGE_CONNECTION_STRING_B64"
```

Update job environment variables:

```bash
az containerapp job update \
  --name cbs-housing-pavel \
  --resource-group rg-hyf-data \
  --set-env-vars \
    API_URL="$API_URL" \
    POSTGRES_URL=secretref:postgres-url \
    AZURE_STORAGE_CONNECTION_STRING_B64=secretref:storage-connection-string-b64 \
    DB_SCHEMA="$DB_SCHEMA" \
    BLOB_CONTAINER="$BLOB_CONTAINER" \
    BLOB_PREFIX="$BLOB_PREFIX" \
    LOG_LEVEL="$LOG_LEVEL"
```

Trigger a manual run for testing (without waiting for the schedule):
```bash
az containerapp job start --name cbs-housing-pavel --resource-group rg-hyf-data
```

## Verify results

Check job execution:

```bash
az containerapp job execution list \
  --name cbs-housing-pavel \
  --resource-group rg-hyf-data \
  --output table
```

Successful execution:

```text
cbs-housing-pavel-nu3xdyf  Succeeded
```

Check job logs:

```bash
az containerapp job logs show \
  --name cbs-housing-pavel \
  --resource-group rg-hyf-data \
  --execution cbs-housing-pavel-nu3xdyf \
  --container cbs-housing-pavel
```

Postgres verification result:

```text
row_count: 500
period_range: ('1995JJ00', '2026KW01')
```

Blob verification result:

```text
blob_count: 6
cbs_housing/2026-06-17_130927.json 1212498
```

Evidence files are stored in the `docs/` directory:

```text
docs/execution_history.txt
docs/job_logs.txt
docs/postgres_verification.txt
docs/blob_verification.txt
```

## Clean up

```bash
az containerapp job delete --name cbs-housing-pavel --resource-group rg-hyf-data --yes
```
