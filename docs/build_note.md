# Build note

## Intentional workflow patterns

**Prompt chaining:** Model A first chooses a primary reason using `PrimaryPrediction`, then extracts `Attributes` using the corresponding sub-taxonomy. Confidence is the minimum of the two stages and ambiguity flags are combined. Removing this split loses independent inspection of primary versus extraction failures.

**Quality routing:** Python compares the validated result with configurable thresholds. Model B re-evaluates low-confidence, ambiguous, or invalid outputs. Disagreements and unresolved predictions enter review. Removing this route either spends the strong-model budget on every record or accepts weak-model uncertainty without scrutiny.

**Technical resilience:** LangChain retry composition retries structured-output or transient failures once. Optional `with_fallbacks` handles exhausted transient transport failures using a separately configured model. It is not triggered by low confidence or schema failure. Without it, provider outages leave more records in visible error/review states. No failure drops a row.

Native structured output is used again on schema retry; no regex parsing or unrestricted repair prompt is used. Taxonomy compatibility and verbatim evidence are checked inside the retried boundary. Costs/logs include attempts, including parse failures with available usage. Transport failures with unknown usage leave the total cost unavailable.

## Components

`ingestion.py`: bounded CSV/XLSX input, validation, source/label isolation.

`schemas.py`, `prompts.py`, `models.py`: Pydantic contracts, versioned LangChain prompts, provider factory.

`pipeline.py`, `routing.py`: sequential fixed workflow, explicit quality rules and technical fallback, call audit.

`analytics.py`, `evaluator.py`, `costing.py`: deterministic analytics with explicit populations and denominators.

`storage.py`: human-edit audit, safe CSV and lossless JSON export.

`demo.py`: intentionally limited local rules, only for offline workflow demonstration.

`app.py`: six-page Streamlit frontend with source drilldowns and review actions.

## Validation and remaining acceptance work

Automated tests verify all 1,000 source records survive the full demo and all 440 Other records finish. The KRT-184 fit/chest cluster and Vendor_12 quality concentration emerge through normal aggregations. UI tests process the full sample, open all result pages, mark a review item unclear, and revisit updated insights.

Live provider quality/latency/cost is not verified without credentials. The offline demo does not establish two-model performance. Production persistence, accounts, concurrency, real-company integrations, and automated business actions are intentionally excluded.

Cloud deployment requires an authenticated Streamlit account connected to the GitHub repository. A local health check or generated deployment link is not proof of Cloud deployment.
