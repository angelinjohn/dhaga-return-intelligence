# Dhaga & Co. Return Intelligence

A Streamlit MVP that turns apparel return comments into product investigation priorities. Built around the supplied 1,000-row synthetic workbook: 440 `Other` records, 560 existing structured reasons.

## Run locally

Requires Python 3.12. From this directory on Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python -m streamlit run app.py
```

macOS/Linux:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

Open http://localhost:8501. The sample is loaded automatically. Open **Upload & Process**, keep **Offline demo**, and click **Run classification**. No credentials or network are required for the offline workflow. The UI includes a local font fallback when Google Fonts cannot load.

On the computer where this project was created, the `.venv` is already installed. Run `start.ps1` with PowerShell to launch the app.

## What is implemented

- CSV and Excel upload, required-field/date/unique-ID checks, empty Other-comment rejection, and visible invalid-file errors.
- LangChain prompt chaining: Model A primary classification, then attribute extraction conditioned on that primary reason.
- Pydantic validation at every model boundary, compatible sub-taxonomies, and source-substring evidence checks.
- Explicit quality escalation at configurable thresholds (A: 0.85; B: 0.80), model disagreement review, and visible unresolved/error states.
- One retry for schema/transient failures. An independently configured technical fallback runs only for transient failures, not low confidence.
- SKU, vendor and category insights, source-comment filters, both model predictions, fit direction/body area breakdowns.
- Confirm, correct and mark-unclear review actions; edits update analytics and retain an audit trail.
- Frozen automated evaluation, confusion matrix, per-call usage/latency/errors and deterministic cost estimates.
- CSV results, JSON run/audit, evaluation and call-log downloads.

The offline demo uses a small keyword classifier to exercise the application. It is **not an LLM**, does not satisfy the two-live-model acceptance criterion, and must not be presented as model-quality evidence. Demo evaluation reports are labeled accordingly. No prediction code looks up expected labels or special-cases a SKU/vendor.

## Live models

Set `OPENAI_API_KEY` in `.env`, then select **Live models** in the app. The default two distinct models are `openai:gpt-4.1-mini` for bulk calls and `openai:gpt-4.1` for difficult cases. These are configurable starting choices: the mini tier is intended to minimize bulk cost, while the stronger tier is reserved for uncertain records. Quality, cost and latency must be measured on an actual live run; none is claimed from offline results.

`MODEL_A_PROVIDER` / `MODEL_A_NAME` and `MODEL_B_PROVIDER` / `MODEL_B_NAME` are independent. The factory uses LangChain `init_chat_model`. The base requirements include only the OpenAI integration. To use another supported provider, install its integration and add it to the deployment requirements, for example `langchain-anthropic` or `langchain-google-genai`, set its API key in the environment, and choose the corresponding LangChain provider identifier. Temperature is explicit for both roles; select models that support the configured temperature and structured output.

Set `MODEL_FALLBACK_NAME` and the corresponding provider/price fields to enable an alternate endpoint after exhausted transient retries. Leave it blank to disable technical fallback. Low confidence always uses the explicit Model B route regardless of this setting. Authentication/configuration errors are visible and are not retried as transient failures.

Enter current provider input/output prices (USD per million tokens) in `.env`. Zero means unconfigured, so cost is **unavailable**, not free. Provider-reported token counts are preferred; missing metadata uses a labeled character-count estimate. Billing estimates do not model cache discounts. Failed calls with unknown usage make total cost unavailable rather than silently understating it.

## Architecture

```text
CSV / Returns_Data worksheet
  -> deterministic validation
  -> source allowlist (evaluation labels stored separately)
  -> Model A primary prompt + Pydantic output
  -> Model A attribute prompt + Pydantic output
  -> explicit confidence router
       -> accept A
       -> Model B full re-evaluation -> accept B / human review
  -> pandas analytics -> evidence -> human corrections
```

There is no agent, autonomous planner, vector database or tool-selection loop. Python owns validation, routing rules, filtering, counting, percentages, evaluation and costs. LangChain owns prompts, model abstraction, structured model calls, retry and technical fallback composition. Processing is sequential to make progress, costs and failures straightforward to audit. A 10,000-row / 10 MB input limit bounds this MVP; the supplied batch is 440 eligible comments.

Human edits are separate from `automated_prediction` and `automated_status`. Review adds the terminal `REVIEWED_HUMAN` state. The 560 non-Other rows retain their dropdowns with `EXISTING_DROPDOWN`, without invented sub-reasons or API calls. Unknown structured dropdowns remain explicitly unmapped.

## Dataset and evaluation caveats

The original workbook is preserved in `data/`. Its `Returns_Data` sheet is also included as a lossless CSV equivalent. `expected_*` fields are isolated at ingestion; only text and dropdown context enter inference. Source columns are displayed, and the evaluator joins hidden labels by return ID after inference.

The workbook uses `defect` where the specification uses `general_defect`. Evaluation normalizes that single documented alias; it never silently rewrites other labels. The supplied synthetic labels may be noisy: for example, some colour comments are labeled print mismatch. Scores therefore characterize agreement with these labels, not verified real-world accuracy. Body-area scoring uses non-`none` expected labels. Metrics display denominators; missing labels produce N/A rather than a false zero.

The client brief's 31% overall return rate is a contextual fact. This file contains returns only, not all units sold. Vendor and SKU metrics use counts or the share of classified returned records, never a sales-based return rate. The application does not claim to reduce returns.

## State and privacy

Data and review changes live in one Streamlit browser session. Export before closing/reloading the session; this is not a persistent production database. JSON preserves full source strings and audit data. CSV exports prefix spreadsheet-formula-like text with an apostrophe to avoid spreadsheet formula execution. Uploaded files are not written to disk by the app. API errors log class names, not provider error bodies or secrets.

LangSmith is optional: set `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, and `LANGSMITH_PROJECT`. Traces contain synthetic comments and sanitized inference payloads, not evaluation labels. Local call logs are available without tracing. Before using real customer data, define retention, PII handling, authentication and access controls. Those production features are outside this synthetic MVP.

## Tests

```powershell
.\.venv\Scripts\python -m pytest -q
```

Tests cover supplied XLSX/CSV equivalence, input rejection, hidden-label isolation, schema and evidence validation, routing boundaries, schema retries, technical fallback, provider failure, disagreement, review/evaluation separation, planted-pattern discovery, export escaping and the complete Streamlit UI journey. Live adapters are exercised with fake structured LangChain responses to avoid API charges. A live-provider acceptance run still needs credentials.

## Deploy

Target: **Streamlit Community Cloud**, Python **3.12**, entrypoint **app.py**. Follow [the deployment guide](docs/deployment.md). The project starts in offline mode and needs no secrets for the hosted demo. No public deployment is claimed until a working Cloud URL is verified.

See [discovery note](docs/discovery_note.md), [build note](docs/build_note.md), and [original specification](docs/requirements.md) for scope and decisions.
