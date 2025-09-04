# CERM Jira LLM Automation

RAG-powered Jira Cloud triage automation using Azure OpenAI and the Pinecone vector database. The app:

- Searches Jira Cloud issues for target comments (keywords in a Jira heading).
- Performs LLM-based triage to score and select the most relevant developer comments.
- Runs vector search in Pinecone to retrieve top‑k reference chunks (metadata: title, text, source).
- Builds a Retrieval‑Augmented Generation (RAG) context and Chat Completions messages (system + user) to produce a concise end‑user reply.
- Publishes the answer to the Jira issue as an Atlassian Document Format (ADF) comment with a References table.

---
![Flowchart Diagram](/resources/images/flowchart/ai-jira-briefing-diagram.svg)
---

## How it works

High-level flow:

1) Query Jira for recent issues that contain specific comment headers (keywords).
2) Ask an Azure OpenAI “triage” deployment to score which comments mattered to the resolution.
3) Embed the issue summary and query Pinecone for top-k related docs (expects metadata: title, text, source).
4) Build a structured prompt (system + user) and call Azure OpenAI to draft the final reply.
5) Post an Atlassian Document Format (ADF) comment to the Jira issue, including an expandable References table.

Key modules:

- `src/main.py` — Orchestrates the full pipeline end-to-end.
- `src/services/gatherer.py` — Jira queries, AI comment filtering, Pinecone search, ADF posting.
- `src/services/controller.py` — Creates Azure OpenAI clients, wraps chat completions.
- `src/services/builder.py` — Compiles the final prompt from comments + docs.
- `src/utils/text.py` — Builds the ADF payload and plain-text fallback.
- `src/config/config.py` — Loads settings from environment; validates and structures configuration.
- `prompt/system.md` — The system prompt used to steer the final response.

Repo layout (selected):

- `init.sh` — Bootstrap script: creates .env, installs requirements, sets pre-commit hooks.
- `requirements.txt` — Python dependencies.
- `test_scripts/` — Connectivity and sanity checks for Azure embeddings, Pinecone, and Jira.

---

## Prerequisites (software and accounts)

- Python 3.11+ (3.12 recommended)
- Git (optional but recommended)
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

---

## Quick start

1) Clone the repo and run the init script:

    ```bash
    ./init.sh
    ```

    This will:
    - Create `.env` in the repo root and also make it available as `src/.env` (the app loads from `src/.env`).
    - Install Python requirements.
    - Install pre-commit hooks (if configured).

2) Open `.env` and fill in all required variables ([see next section](#configuration-env)).

3) Validate connectivity (optional but recommended):

   - Azure embeddings: `python test_scripts/embeddings_model.py`
   - Pinecone search: `python test_scripts/pinecone_connection.py`
   - Jira search: `python test_scripts/pull_jira_comments.py`
   - Post a sample ADF comment: `python test_scripts/jira_adf_message.py`

4) Run the pipeline:

    ```bash
    python src/main.py
    ```

---

## Configuration (.env)

The app loads environment variables from `src/.env`. The template is at `.env.template`.

Jira (basic auth):

- `JIRA_SERVER`: Base URL of your Jira Cloud site, e.g. `https://your-domain.atlassian.net`
- `JIRA_EMAIL`: Your Atlassian account email
- `JIRA_API_TOKEN`: Create at <https://id.atlassian.com/manage-profile/security/api-tokens>
- `JIRA_USER_AGENT`: Arbitrary user agent string for API requests

Azure OpenAI (provide api-version via the endpoint URL):

- `AZURE_OPENAI_API_KEY`: Azure OpenAI API key from your resource (Azure Portal > Keys & Endpoint)
- `AZURE_ENDPOINT`: Base resource endpoint with `api-version` as a query param, e.g.
  - `https://your-openai-resource.openai.azure.com/?api-version=2024-06-01`
- `AZURE_DEPLOYMENT_NAME`: Deployment name for the final chat model (e.g., `gpt-4o-mini`)

Triage (separate or same Azure OpenAI resource):

- `AZURE_TRIAGE_ENDPOINT`: Endpoint with `api-version`, e.g. `https://...azure.com/?api-version=2024-06-01`
- `AZURE_TRIAGE_DEPLOYMENT_NAME`: Deployment name for triage comment selection

Embeddings:

- `AZURE_EMBEDDING_ENDPOINT`: Endpoint with `api-version`, e.g. `https://...azure.com/?api-version=2024-06-01`
- `AZURE_EMBEDDING_DEPLOYMENT_NAME`: Embedding deployment name (e.g., `text-embedding-3-small`)
- `AZURE_EMBEDDING_DIMENSION`: Optional; defaults to 1536

Pinecone:

- `PINECONE_API_KEY`: Project API key (Pinecone Console > API Keys)
- `PINECONE_INDEX`: Existing index name to query
- `PINECONE_NAMESPACE`: Namespace inside the index (used to segment data)

Logging (optional):

- `LOG_NAME`: Logger name (default `Cerm7-AI-project`)
- `LOG_LEVEL`: e.g., `INFO`, `DEBUG`
- `LOG_DATEFMT`: e.g., `%Y-%m-%d %H:%M:%S`

Project JQL controls:

- `AIR_SEARCH_PROJECTS`: Comma-separated Jira project keys, e.g., `PROJ1, PROJ2`
- `AIR_SEARCH_KEYWORDS`: Comma-separated keywords; the app looks for comments that start with a Jira heading containing any keyword (e.g., a comment whose first line is `h2. Online Help`)

Notes about Azure api-version:

- The code extracts the `api-version` from the endpoint URLs. Make sure each Azure endpoint includes `?api-version=YYYY-MM-DD`.
- If you omit it, Azure OpenAI calls will fail. Keep the base endpoint format (no deployment path).

---

## Validating the setup

- Embeddings only: `python test_scripts/embeddings_model.py`
- Pinecone round-trip: `python test_scripts/pinecone_connection.py`
- Jira search (JQL built from env): `python test_scripts/pull_jira_comments.py`
- Post a fixed ADF payload to a known issue: `python test_scripts/jira_adf_message.py` (edit `issue_key` in the script)

---

## Run details

When you run `python src/main.py`:

1) JQL is built from `AIR_SEARCH_PROJECTS` and `AIR_SEARCH_KEYWORDS` and issues are fetched.
2) Comments are filtered by the triage model (scores >= 0.5 are kept).
3) Pinecone is queried with the issue summary to get top-k references (default 10).
4) A final prompt is compiled and sent to the main chat deployment.
5) The generated text is posted to Jira as an ADF comment with an expandable “References” table.

Expectations for Pinecone metadata:

- Each match must have `metadata.title`, `metadata.text`, and `metadata.source`.
- If these are missing, posting a useful References table will fail or be empty.

---

## Troubleshooting

- Jira 401/403: verify `JIRA_SERVER`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, and permissions to comment.
- Azure OpenAI errors: ensure each endpoint includes `?api-version=...` and deployment names match exactly.
- Pinecone index errors: confirm `PINECONE_INDEX` exists, API key is correct, and the index contains data in the chosen `PINECONE_NAMESPACE`.
- No matching issues/comments: adjust `AIR_SEARCH_PROJECTS` and `AIR_SEARCH_KEYWORDS` to match your data.
- Env not loading: make sure `src/.env` exists; the init script creates it for you.

---

## Development

- Formatting: Black and isort are included. Pre-commit is installed by `./init.sh` if available.
- System prompt lives in `prompt/system.md`.
- Generated prompts for each processed issue are saved under `prompt/issues/<ISSUE-KEY>/prompt.json`.

---

## License

Internal project.
