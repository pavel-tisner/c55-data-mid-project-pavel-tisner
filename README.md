# Week 7 Project: CBS Dutch Housing Purchase Prices Pipeline

## What it does

This project is a data engineering pipeline for Dutch housing purchase price data from the CBS Open Data API.

The pipeline fetches CBS housing records and CBS region lookup records, validates both with Pydantic, transforms and enriches the data with pandas, stores transformed rows in Azure Postgres, and uploads the raw housing API response to Azure Blob Storage.

The region lookup adds a human-readable `region_name` column while keeping `region_code` as the stable CBS source identifier.

## Data source

CBS Open Data API, dataset `85792ENG`.

Main housing records:

```text
https://opendata.cbs.nl/ODataApi/odata/85792ENG/TypedDataSet
```

Region lookup records:

```text
https://opendata.cbs.nl/ODataApi/odata/85792ENG/Regions
```

## Architecture

```text
CBS TypedDataSet API ──► housing records
CBS Regions API ───────► region lookup
                              │
                              ▼
pipeline.py
  ├──► Pydantic validation
  │       - validate housing records
  │       - validate region lookup records
  ├──► pandas transformation
  │       - rename CBS technical columns
  │       - parse period_year
  │       - parse period_type
  │       - parse period_quarter
  │       - convert numeric columns
  │       - enrich housing records with region_name
  ├──► Azure Postgres
  │       schema: dev_pavel_tisner
  │       table: cbs_housing_purchase_prices
  └──► Azure Blob Storage
          container: raw
          prefix: cbs_housing
```

## Possible analysis: housing market signal

The transformed table can be used to compare price movement with transaction volume. This is useful because housing prices alone do not tell the full story. A market where prices are rising and transactions are also rising is different from a market where prices are rising but fewer dwellings are being sold.

The pipeline prepares the following analysis-ready columns:

* `region_code` — stable CBS region identifier
* `region_name` — human-readable region name from the CBS Regions lookup endpoint
* `average_purchase_price` — average purchase price of dwellings
* `number_of_dwellings_sold` — transaction volume
* `change_price_previous_period` — price change compared with the previous period
* `change_sales_previous_period` — sales volume change compared with the previous period
* `change_price_previous_year` — price change compared with the same period in the previous year
* `change_sales_previous_year` — sales volume change compared with the same period in the previous year
* `period_year`, `period_type`, `period_quarter` — parsed time fields for yearly and quarterly analysis

A possible market signal can be interpreted as follows:

- **Price up + transactions up**: strong active market. Buyers may face more competition and may need to move faster. Sellers are usually in a stronger position.

- **Price up + transactions down**: prices are still rising, but liquidity may be weakening. Buyers can question asking prices more carefully. Sellers should avoid overpricing.

- **Price down + transactions up**: the market may be becoming more accessible and liquid. Buyers may find more opportunities. Sellers can still sell if pricing is realistic.

- **Price down + transactions down**: weak market signal. Buyers may have more bargaining power, but should watch market risk. Sellers may need more flexibility.

### Example SQL query

The example below uses quarterly records and year-over-year changes. This avoids comparing seasonal quarters directly, for example Q1 against Q4.

```sql
SELECT
    region_name,
    period,
    period_year::text AS period_year,
    'Q' || period_quarter::text AS period_label,
    average_purchase_price,
    number_of_dwellings_sold,
    change_price_previous_year,
    change_sales_previous_year,
    CASE
        WHEN change_price_previous_year > 0
             AND change_sales_previous_year > 0
            THEN 'prices up, transactions up: strong active market'
        WHEN change_price_previous_year > 0
             AND change_sales_previous_year < 0
            THEN 'prices up, transactions down: weaker liquidity'
        WHEN change_price_previous_year < 0
             AND change_sales_previous_year > 0
            THEN 'prices down, transactions up: more accessible/liquid market'
        WHEN change_price_previous_year < 0
             AND change_sales_previous_year < 0
            THEN 'prices down, transactions down: weak market'
        ELSE 'mixed or missing year-over-year data'
    END AS market_signal
FROM dev_pavel_tisner.cbs_housing_purchase_prices
WHERE period_type = 'quarter'
  AND average_purchase_price IS NOT NULL
  AND number_of_dwellings_sold IS NOT NULL
ORDER BY
    period_year DESC,
    period_quarter DESC,
    region_name;
```

These signals are possible interpretations, not proof of causality. Housing market dynamics also depend on interest rates, mortgage rules, supply, income, dwelling types, and regional differences.

## Run locally

Create `.env` from `.env.example` and fill it with your own values from Azure Key Vault.

My local `.env` uses exported variables:

```bash
export API_URL="https://opendata.cbs.nl/ODataApi/odata/85792ENG/TypedDataSet"
export REGIONS_URL="https://opendata.cbs.nl/ODataApi/odata/85792ENG/Regions"
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

### Install dependencies
```bash
uv sync
```

### Run directly (without Docker)
```bash
uv run python -m src.pipeline
```

### Or build and run with Docker
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
    REGIONS_URL="$REGIONS_URL" \
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
cbs-housing-pavel-zheh8po  Succeeded
```

Check job logs:

```bash
az containerapp job logs show \
  --name cbs-housing-pavel \
  --resource-group rg-hyf-data \
  --execution cbs-housing-pavel-zheh8po \
  --container cbs-housing-pavel
```

Postgres verification result:

```text
row_count: 500
rows_with_region_name: 500
period_range: ('1995JJ00', '2026KW01')
```

Blob verification result:

```text
blob_count: 6
cbs_housing/2026-06-17_190932.json 1212498
```

Evidence files are stored in the `docs/` directory:

```text
docs/execution_history.txt
docs/job_logs_region_names.txt
docs/job_logs.txt
docs/postgres_verification.txt
docs/blob_verification.txt
```

## Clean up

```bash
az containerapp job delete --name cbs-housing-pavel --resource-group rg-hyf-data --yes
```
