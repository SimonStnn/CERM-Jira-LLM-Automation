<!-- omit from toc -->
# CERM Jira LLM Automation

RAG-powered Jira Cloud triage automation using Azure OpenAI and the Pinecone vector database. The app:

- Searches Jira Cloud issues for target comments (keywords in a Jira heading).
- Performs LLM-based triage to score and select the most relevant developer comments.
- Runs vector search in Pinecone to retrieve top‑k reference chunks (metadata: title, text, source).
- Builds a Retrieval‑Augmented Generation (RAG) context and Chat Completions messages (system + user) to produce a concise end‑user reply.
- Publishes the answer to the Jira issue as an Atlassian Document Format (ADF) comment with a References table.

## How it works

![Flowchart Diagram](/resources/images/flowchart/ai-jira-briefing-diagram.png)

High-level flow:

1) Query Jira for recent issues that contain specific comment headers (keywords).
2) Ask an Azure OpenAI “triage” deployment to score which comments mattered to the resolution.
3) Embed the issue summary and query Pinecone for top-k related docs (expects metadata: title, text, source).
4) Build a structured prompt (system + user) and call Azure OpenAI to draft the final reply.
5) Post an Atlassian Document Format (ADF) comment to the Jira issue, including an expandable References table.

## Table of contents

- [How it works](#how-it-works)
- [Table of contents](#table-of-contents)
- [Prerequisites (software and accounts)](#prerequisites-software-and-accounts)
- [Setup](#setup)
  - [File Setup](#file-setup)
  - [Env Setup](#env-setup)
    - [Jira](#jira)
    - [Azure OpenAI](#azure-openai)
    - [Pinecone](#pinecone)
    - [Search / Project Scope](#search--project-scope)
  - [Reference documents in Pinecone](#reference-documents-in-pinecone)
- [Run details](#run-details)
  - [Automated pipeline execution](#automated-pipeline-execution)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [License](#license)

## Prerequisites (software and accounts)

- Python 3.12
- Jira Cloud account with:
  - Access to the target projects
  - “Browse Projects” and “Add Comments” permissions
  - An Atlassian API token
- Azure OpenAI (Azure AI Foundry) access with three deployments:
  - Chat deployment for the final answer (e.g., `gpt-5-mini`/`gpt-4.1-mini`)
  - Chat deployment for “triage” comment selection (can be the same or a lighter model)
  - Embeddings deployment (e.g., `text-embedding-3-small`)
- Pinecone project with an index populated with document chunks and metadata fields:
  - `title` (string)
  - `text` (string)
  - `source` (URL or identifier)

Network access to Jira Cloud, Azure OpenAI endpoints, and Pinecone is required.

## Setup

### File Setup

```bash
./init.sh
```

If you prefer manual steps:

```bash
cp .env.template .env
pip install -r requirements.txt
pre-commit install
```

[Then fill out the environment variables](#env-setup) and run:

```bash
python src/main.py
```

### Env Setup

Below are all configuration variables consumed from the `.env`. The application loads them early via `src/config/config.py` (Pydantic models). Missing REQUIRED values will cause validation errors or failed API calls.

#### Jira

These authenticate to Jira Cloud using basic auth (email + API token).

- `JIRA_SERVER`
  > Base URL of your Jira Cloud site. Example: `https://your-domain.atlassian.net`
- `JIRA_EMAIL`
  > Atlassian account email used with the API token
- `JIRA_API_TOKEN`
  > Create at: <https://id.atlassian.com/manage-profile/security/api-tokens>
- `JIRA_USER_AGENT`
  > Custom user agent string; helps identify traffic. (default: `AI-project`)

#### Azure OpenAI

These variables are found in your [Azure AI Foundry](https://ai.azure.com/). From here go to your [resource](https://learn.microsoft.com/en-us/azure/ai-services/multi-service-resource?pivots=azportal). You will to [deploy a model](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-models/how-to/create-model-deployments?pivots=ai-foundry-portal). For this app you will need a "Chat completion" (eg. `gpt-5-mini`) and an "Embeddings" model (eg. `text-embedding-3-small`).

The embedding model should match the one used in your Pinecone project.

This model will be used for the report generation.

- `AZURE_OPENAI_API_KEY`
  > Go to "Overview". Here you can find your Azure API Key.
- `AZURE_ENDPOINT`
  > Go to "My assets > Model deployments". Click your Chat completion model. Copy the "Target URI".
  > This endpoint should end with `?api-version=YYYY-MM-DD`. Example: `https://your-openai-resource.openai.azure.com/?api-version=2024-06-01`
- `AZURE_DEPLOYMENT_NAME`
  > Go to "My assets > Model deployments". Copy the name of the model deployment (eg. `gpt-5-mini`).

Used to score/filter relevant Jira comments before building the final answer. Can point to a lighter or the same model.

- `AZURE_TRIAGE_ENDPOINT`
  > Endpoint with `api-version` query param (same format as above) (REQUIRED for triage step)
- `AZURE_TRIAGE_DEPLOYMENT_NAME`
  > Go to "My assets > Model deployments". Copy the name of the model deployment (eg. `gpt-4.1-mini`).

Creates vector embeddings for issue summaries / queries used in Pinecone similarity search.

- `AZURE_EMBEDDING_ENDPOINT`
  > Go to "My assets > Model deployments". Click your Embeddings model. Copy the "Target URI".
- `AZURE_EMBEDDING_DEPLOYMENT_NAME`
  > Go to "My assets > Model deployments". Copy the name of the model deployment (eg. `text-embedding-3-small`).

#### Pinecone

The app will connect to a Pinecone project. This project should contain an index for the context you want the app to have access to (eg. your vectorized documentation). [More info](#reference-documents-in-pinecone)

- `PINECONE_API_KEY`
  > Go to the [Pinecone console](https://app.pinecone.io/organizations/-/projects). Select your project. Go to "API Keys". Click "Create API Key". [More info](https://docs.pinecone.io/guides/projects/manage-api-keys)
- `PINECONE_NAMESPACE`
  > Copy your Pinecone Namespace
- `PINECONE_INDEX`
  > Go to the [Pinecone console](https://app.pinecone.io/organizations/-/projects). Select your project. Navigate to your index. Copy the name of the index.

#### Search / Project Scope

Controls the root logger referenced by `settings.log`.

- `LOG_NAME`
  > Logger name (default: `AI-project`)
- `LOG_LEVEL`
  > Logging level (e.g., `INFO`, `DEBUG`, `WARNING`) (default: `INFO`)

- `AIR_SEARCH_JQL`
  > Full JQL string defining target issues (REQUIRED)
  > The pipeline queries Jira issues via JQL. Prefer supplying a full JQL expression. If `AIR_SEARCH_JQL` is empty the app will fail validation.
- `AIR_SEARCH_PROJECT`
  > Project key used when resolving linked issues / context (default: `CERM7`)

---

Notes:

- Every Azure endpoint MUST include `?api-version=...` (the code extracts it automatically).
- Keep secrets (API keys / tokens) out of commits; `.env` is git‑ignored.
- If you rotate keys, restart the process so Pydantic reloads values.

### Reference documents in Pinecone

Documents should include `title`, `text`, and `source` metadata. The assistant turns the summary into a short query and fetches top‑k matches within your `PINECONE_NAMESPACE`. The reply includes a simple list of unique sources.

## Run details

When you run `python src/main.py`:

1) Issues are fetched using `AIR_SEARCH_JQL`.
2) Comments are filtered by the triage model (scores >= 0.5 are kept).
3) Pinecone is queried with the issue summary to get top-k references (default 10).
4) A final prompt is compiled and sent to the main chat deployment.
5) The generated text is posted to Jira as an ADF comment with an expandable “References” table.

### Automated pipeline execution

An Azure DevOps pipeline (`pipelines/daily_pipeline-run-application.yml`) also runs the workflow on a schedule:

- `trigger: none` – pushes to `main` do not auto‑run; execution is either scheduled or manual.
- `schedules.cron: 0 4 * * SAT` – runs every Saturday at 04:00 UTC (Azure DevOps hosted cron uses UTC).
- Variable group: `jira-ai-project-variables-group` supplies the secret values that mirror the `.env` entries (API keys, endpoints, etc.). Maintain them in the library, not in source.
- Steps: install dependencies, run the app (`python3.11 src/main.py`), detect the latest date‑based log directory, then publish it as a pipeline artifact.
- Resilience: `continueOnError: true` on the run step ensures log collection + artifact publish still occur even if the main script exits non‑zero.

Artifacts contain the structured logs under `log/<YYYY>/<MM>/<DD>/` including:

- `cerm7-ai-project.log` (runtime log)
- `jira_issues.json` (queried issues snapshot)
- Per‑issue subfolders with prompt + model output for traceability
- `cerm7-ai-project.log` (runtime log)
- `jira_issues.json` (queried issues snapshot)
- Per‑issue subfolders with prompt + model output for traceability

Manual run: Use “Run pipeline” in Azure DevOps to execute ad‑hoc (e.g., after changing variable values or model deployments). To change cadence, edit the cron string (UTC) and commit. If you want push‑based execution, replace `trigger: none` with a branch include list.

Security note: keep secrets exclusively in the variable group; the repo only references variable names.

## Troubleshooting

- Jira 401/403: verify `JIRA_SERVER`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, and permissions to comment.
- Azure OpenAI errors: ensure each endpoint includes `?api-version=...` and deployment names match exactly.
- Pinecone index errors: confirm `PINECONE_INDEX` exists, API key is correct, and the index contains data in the chosen `PINECONE_NAMESPACE`.
- No matching issues/comments: adjust `AIR_SEARCH_JQL` (and optionally `AIR_SEARCH_PROJECT`) to match your data.
- Env not loading: make sure `src/.env` exists; the init script creates it for you.

## Development

- Formatting: Black and isort are included. Pre-commit is installed by `./init.sh` if available.
- System prompt lives in `prompt/system.md`.
- Generated prompts for each processed issue are saved under `prompt/issues/<ISSUE-KEY>/prompt.json`.

## License

Internal project.
