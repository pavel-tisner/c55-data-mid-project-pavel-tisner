# AI Assistance Log

Document every time you used an AI tool during this project: what you asked, what it gave you, and what you changed before using it.

This is not about proving you worked hard. It is about building the habit of treating AI output as a first draft, not a final answer.

## Tools used

ChatGPT

-

## Log

### Entry 1

**What I asked:** I asked ChatGPT to help me choose a suitable live API dataset for the Week 7 data engineering project. I wanted a dataset related to Dutch housing or real estate that would be suitable for a pipeline with validation, transformation, Postgres storage, and Blob Storage.

**What it gave me:** ChatGPT helped me identify a CBS Open Data API dataset about Dutch dwelling purchase prices. It explained the structure of the API response and helped me understand the meaning of the CBS fields, such as regions, periods, price index, number of dwellings sold, average purchase price, and total purchase value.

**What I changed:** I tested the API myself with Python and confirmed that it returned 3276 records. I inspected the first record manually and selected the final project focus myself: Dutch housing purchase prices by region and period. I also chose the research question: how Dutch dwelling purchase prices and sales volumes change across regions and periods.

### Entry 2 — Limiting the transformed Postgres output to 500 rows

**What I asked:** During local testing, the pipeline fetched and validated all 3276 records successfully, but the first Postgres insert attempt was too slow and appeared to hang. I asked ChatGPT how to debug this without overcomplicating the project.

**What it gave me:** ChatGPT helped me separate the problem into smaller parts: first verify that the API and validation worked, then check the pandas transformation, then reduce the amount of data inserted into Postgres for the MVP. It suggested storing the latest 500 transformed rows in Postgres while still uploading the full raw API response to Blob Storage.

**What I changed:** I decided to keep the full raw API response in Blob Storage, because that preserves the complete source data. For Postgres, I limited the transformed dataset to the latest 500 rows using the CBS record ID. This made the scheduled job lightweight and reliable while still demonstrating the full pipeline: fetch, validate, transform, insert, and upload.

### Entry 3 — Debugging failed Azure Container App Job executions

**What I asked:** After the local pipeline and Docker run worked, I deployed the image to Azure Container App Job. The first two manual executions failed. I asked ChatGPT to help me interpret the Azure job logs and identify the problem.

**What it gave me:** ChatGPT helped me read the job logs and narrow down the issue. The container was starting correctly, the API fetch worked, validation worked, transformation worked, and the pipeline inserted rows into Postgres. The failure happened only at the Blob Storage upload step. The logs showed:

KeyError: 'ACCOUNTNAME'
ValueError: Connection string missing required connection details.

ChatGPT explained that this was probably not a Docker image architecture problem, because the container had already started and executed Python code. The likely issue was the Azure Storage connection string.

**What I changed:** I checked the environment variable locally and found that the storage connection string was truncated after DefaultEndpointsProtocol=https. The root cause was that Azure Storage connection strings contain semicolons, so they must be quoted carefully in .env and handled carefully in Azure Container App Job environment variables.

To make the Azure deployment more reliable, I added support for a base64-encoded storage connection string:

AZURE_STORAGE_CONNECTION_STRING_B64

The pipeline now checks for AZURE_STORAGE_CONNECTION_STRING_B64, decodes it, and uses it for Azure deployment. For local runs, it can still use the normal AZURE_STORAGE_CONNECTION_STRING.

After updating the Azure Container App Job secret and environment variables, the next manual execution succeeded:

cbs-housing-pavel-nu3xdyf  Succeeded
---
