# Dhaga & Co. Return Reason Intelligence MVP
## Product & Engineering Requirements

**Document status:** MVP build specification — LangChain architecture revision  
**Primary user:** Neha, Category Head  
**Project type:** Forward Deployed Engineer mini-project  
**Purpose:** Hand-off specification for a coding agent  
**Scope:** Synthetic-data MVP only; no production integration with Dhaga & Co. systems

## Architecture Decision

**LangChain is required for the LLM orchestration layer in this MVP.**

Use LangChain intentionally for:

- prompt templates and chain composition
- model abstraction across providers
- structured output bound to Pydantic schemas
- prompt chaining
- explicit confidence-based routing
- technical fallbacks
- retries where appropriate
- optional but recommended LangSmith tracing

Do **not** use a LangChain agent for this MVP.

The workflow is deterministic and known in advance:

```text
classify
-> extract
-> validate
-> route
-> aggregate
-> review
```

An autonomous agent would add unnecessary complexity and make failure behavior harder to reason about.

Deterministic analytics, counting, filtering, aggregation, thresholds, evaluation, and cost arithmetic must remain in normal Python/pandas code.

---

## 1. Executive Summary

Dhaga & Co. has an overall return rate of **31%**. Return reasons are captured using a dropdown plus an **"Other"** free-text field, and **44% of returns currently land in "Other"**. The Category Head manually reads a small sample of these comments and believes many are related to fit, but this process does not scale.

The MVP must turn messy free-text return comments into **structured, reviewable, actionable product intelligence**.

The core user question is:

> **Which products are being returned for which reasons, and which issues should I investigate first?**

The MVP must **not** claim to reduce returns directly. It should demonstrate that Dhaga can convert ambiguous return feedback into a reliable taxonomy, identify recurring patterns by SKU/category/vendor, and surface low-confidence cases for human review.

---

## 2. Problem Statement

Dhaga & Co. cannot reliably understand why customers return products because a large share of return reasons is captured as unstructured "Other" text.

This creates three operational problems:

1. The Category Head cannot review all return feedback manually.
2. Recurring issues such as fit, fabric, colour, or defects are difficult to quantify.
3. Product-level or vendor-level patterns are discovered slowly or not at all.

The MVP should convert unstructured feedback into structured intelligence without hiding uncertainty.

---

## 3. Goals

The MVP must:

- Accept a realistic batch of return records from CSV.
- Preserve and display the original return data.
- Identify rows whose dropdown reason is `Other`.
- Classify free-text return comments into a defined taxonomy.
- Extract useful structured attributes such as fit direction and body area.
- Use a cheap model for bulk classification.
- Route ambiguous or low-confidence cases to a stronger second model.
- Route unresolved cases to a human review queue.
- Validate every model response against a structured schema.
- Surface actionable insights by SKU, category, vendor, and return reason.
- Allow a user to drill down from an insight to the original customer comments.
- Measure classification quality using hidden synthetic ground-truth labels.
- Show cost, latency, escalation rate, and failure rate.
- Fail visibly rather than silently producing a wrong result.
- Be usable from a visible frontend deployed to a URL.
- Be runnable locally from the repository by a new developer within five minutes.

---

## 4. Non-Goals

The MVP must **not**:

- Predict whether a new order will be returned.
- Predict customer lifetime value or repeat purchase.
- Automatically approve refunds.
- Modify product listings automatically.
- Contact vendors automatically.
- Change size charts automatically.
- Trigger customer communications.
- Integrate with real Freshdesk, Unicommerce, Postgres, WhatsApp, or other Dhaga systems.
- Claim that the MVP reduces the company's 31% return rate.
- Use the LLM for arithmetic, aggregation, percentages, filtering, or lookup.
- Send hidden ground-truth labels to the classifier.

---

## 5. Source Facts vs Synthetic Assumptions

### 5.1 Facts from the client brief

The implementation and demo should treat the following as client facts:

- Overall returns: **31%**
- Return reasons are captured using a dropdown plus an `"Other"` free-text box.
- **44%** of returns are recorded as `"Other"`.
- Neha manually reads a limited number of `"Other"` comments.
- Neha observes that many manually reviewed comments appear related to fit.
- Customer input may contain Hinglish and messy natural language.
- The company has no ML engineer.
- The solution must be inexpensive and operable by a small engineering team.
- Customer-facing AI output must either be safe to publish unread or include a deliberate human-review step.

### 5.2 Synthetic assumptions used in the MVP dataset

The provided synthetic dataset contains **1,000 returned-order records**.

Exactly:

- `440` records use `return_reason_dropdown = "Other"` (**44%**)
- `560` records use a structured dropdown reason

Within the 440 `"Other"` records, the synthetic test distribution is:

| Synthetic category | Count | % of Other |
|---|---:|---:|
| Fit | 240 | 54.5% |
| Quality / fabric | 55 | 12.5% |
| Appearance / colour | 35 | 8.0% |
| Wrong / damaged | 25 | 5.7% |
| Changed mind | 20 | 4.5% |
| Delivery-related | 18 | 4.1% |
| Other classifiable | 25 | 5.7% |
| Ambiguous / unclear | 22 | 5.0% |

These percentages are **synthetic test assumptions**, not stated client facts.

The dataset also contains deliberately planted patterns:

- `KRT-184` has a concentrated **too-small / chest** issue.
- `Vendor_12` has a disproportionately high number of **fabric / quality** complaints.
- Some comments are intentionally ambiguous and should reach human review.

---

## 6. Primary User

### 6.1 Persona

**Name:** Neha  
**Role:** Category Head

### 6.2 Current workflow

Today Neha:

1. Receives return data containing dropdown reasons and free text.
2. Manually samples `"Other"` comments.
3. Tries to infer common themes.
4. Cannot review the full population.
5. Lacks a consistent quantified view by SKU, category, or vendor.

### 6.3 Desired workflow

Neha should be able to:

1. Upload a return CSV.
2. See whether the dataset is valid.
3. Process all `"Other"` comments.
4. Review the resulting reason distribution.
5. Identify high-signal SKUs/vendors/categories.
6. Drill into original comments.
7. Review or correct uncertain classifications.
8. Export or inspect the structured results.

---

## 7. MVP User Journey

The frontend should expose four primary stages:

1. **Upload**
2. **Process**
3. **Insights**
4. **Review Queue**

### 7.1 Upload

User uploads a CSV.

The application must display:

- total rows
- number of `"Other"` rows
- percentage of `"Other"` rows
- number of unique SKUs
- number of categories
- number of vendors
- missing required fields
- rows with empty return text where text is required

The application must refuse to process invalid files and show the validation error visibly.

### 7.2 Process

User selects **Run classification**.

The app processes the unstructured records and displays progress.

For every applicable row, the system must:

1. classify the primary reason
2. classify the sub-reason
3. extract body area where relevant
4. generate a confidence estimate
5. determine whether a stronger model is needed
6. determine whether human review is needed
7. validate the returned JSON/schema

The user should be able to see:

- processed count
- accepted by Model A
- escalated to Model B
- sent to human review
- schema failures
- processing errors
- estimated cost
- elapsed time

### 7.3 Insights

The Insights screen must show at minimum:

- decomposed `"Other"` reasons
- top primary reasons
- top fit sub-reasons
- top affected SKUs
- top affected vendors
- top affected categories
- fit issues by body area
- percentage of cases routed to review
- percentage successfully classified

The user must be able to click or select an insight and view the source comments behind it.

### 7.4 Review Queue

The Review Queue must show unresolved or low-confidence cases.

For each item show:

- return ID
- SKU
- product
- vendor
- original dropdown reason
- original free-text comment
- Model A prediction
- Model B prediction, if used
- confidence
- final current category
- reason for review

User actions:

- **Confirm**
- **Change primary reason**
- **Change sub-reason**
- **Change body area**
- **Mark unclear**

Corrections must update the final classification used by the dashboard.

---

## 8. Input Data Contract

The MVP input file should support the following columns:

| Column | Required | Description |
|---|---|---|
| `return_id` | Yes | Unique return identifier |
| `order_id` | Yes | Order identifier |
| `sku` | Yes | Product SKU |
| `product_name` | Yes | Product name |
| `category` | Yes | Product category |
| `vendor` | Yes | Supplier/vendor identifier |
| `size_ordered` | No | Ordered size |
| `return_reason_dropdown` | Yes | Existing structured return reason |
| `return_reason_text` | Conditional | Free-text reason, especially for `Other` |
| `return_date` | Yes | Return date |

The synthetic dataset also contains:

| Evaluation-only column | Description |
|---|---|
| `expected_primary_reason` | Hidden ground truth |
| `expected_sub_reason` | Hidden ground truth |
| `expected_body_area` | Hidden ground truth |

### Critical rule

The three `expected_*` fields must **never be sent to the model**.

They may only be used by the evaluator after inference.

---

## 9. Classification Taxonomy

Use a deliberately small taxonomy.

### 9.1 Primary reasons

```text
fit
quality_issue
appearance_issue
wrong_item
damaged_defective
changed_mind
delivery_issue
product_not_as_expected
unclear
```

### 9.2 Suggested sub-reasons

#### fit

```text
too_small
too_large
too_long
too_short
unspecified_fit
```

#### quality_issue

```text
fabric_quality
material_mismatch
comfort
stitching_quality
other_quality
```

#### appearance_issue

```text
colour_mismatch
shade_mismatch
print_mismatch
other_appearance
```

#### wrong_item

```text
wrong_product_or_variant
```

#### damaged_defective

```text
stitching
zip
hole
button
general_defect
```

#### changed_mind

```text
preference_or_no_longer_needed
```

#### delivery_issue

```text
late_delivery
package_damage
other_delivery
```

#### product_not_as_expected

```text
style_mismatch
transparency
occasion_unsuitable
comfort
shrinkage_concern
other_expectation_mismatch
```

#### unclear

```text
insufficient_information
```

### 9.3 Body area

Use only where supported by the comment.

```text
chest
waist
hips
shoulder
sleeves
length
thigh
neck
none
```

Do not infer a body area that is not stated or strongly implied.

---

## 10. Structured Output Schema

Every model boundary must return validated structured output.

Suggested schema:

```json
{
  "primary_reason": "fit",
  "sub_reason": "too_small",
  "body_area": "chest",
  "confidence": 0.93,
  "needs_review": false,
  "evidence_text": "chest se tight hai",
  "explanation": "Customer explicitly describes tightness around the chest."
}
```

### 10.1 Field requirements

#### `primary_reason`

- enum
- required

#### `sub_reason`

- enum compatible with primary reason
- required

#### `body_area`

- enum
- use `none` when not relevant or not stated

#### `confidence`

- float between `0.0` and `1.0`
- model-provided signal used for routing
- do not treat as calibrated probability unless calibration is separately demonstrated

#### `needs_review`

- boolean
- true when the record is ambiguous, contradictory, or unsupported

#### `evidence_text`

- short substring or concise excerpt from the customer's input
- must be grounded in input
- must not invent evidence

#### `explanation`

- short internal explanation
- not customer-facing

---

## 11. Workflow Architecture

The LLM workflow must be implemented using **LangChain**.

The required workflow must use at least two purposeful patterns:

1. **Prompt chaining**
2. **Routing**

LangChain should act as the orchestration layer. It should not own deterministic analytics.

### 11.1 High-level flow

```text
CSV Upload
   |
   v
Deterministic validation (Python/pandas)
   |
   v
Select applicable records
   |
   v
LangChain Prompt Template
   |
   v
Model A: primary classification
   |
   v
LangChain structured output -> Pydantic schema
   |
   v
Model A: attribute extraction / chained step
   |
   v
LangChain structured output -> Pydantic schema
   |
   v
Deterministic routing decision
   |-----------------------------|
   |                             |
High confidence              Low / ambiguous
   |                             |
   v                             v
Accept                    Model B re-evaluation
                                 |
                                 v
                       Structured output validation
                                 |
                           |-------------|
                           |             |
                       Resolved       Unresolved
                           |             |
                           v             v
                         Accept     Human review
                           \             /
                            \           /
                             v         v
                           Final result
                                |
                                v
                    Deterministic aggregation
                                |
                                v
                       Insights dashboard
```

### 11.2 LangChain responsibilities

LangChain must be used for:

- prompt construction
- provider/model abstraction
- chained model steps
- structured outputs
- model invocation
- model fallbacks
- retry composition where appropriate

LangChain should **not** be used to hide the core routing rules. Confidence-based escalation must remain explicit and inspectable.

### 11.3 Non-agent requirement

Do not use:

- `AgentExecutor`
- tool-choosing agents
- ReAct loops
- autonomous planning
- open-ended tool selection

This MVP is a fixed workflow, not an agentic system.

## 12. Prompt Chaining Requirement

Do not use one oversized prompt to perform all tasks.

Recommended chain:

### Step A — Primary classification

Input:

- return text
- optional existing dropdown context
- taxonomy definitions

Output:

- primary reason
- confidence
- ambiguity flag

### Step B — Attribute extraction

Only after primary classification.

Input:

- original comment
- primary reason
- relevant sub-taxonomy

Output:

- sub-reason
- body area
- supporting evidence
- confidence

### Why

This makes:

- errors easier to inspect
- schemas smaller
- prompts easier to test
- model behavior easier to explain
- evaluation possible at multiple stages

---

## 13. Routing Requirement

Use a cheap/fast model as **Model A** and a stronger/more expensive model as **Model B**.

### Suggested routing behavior

Initial default threshold:

```text
confidence >= 0.85 AND needs_review == false
    -> accept Model A

confidence < 0.85 OR needs_review == true
    -> escalate to Model B
```

After Model B:

```text
confidence >= 0.80 AND needs_review == false
    -> accept Model B

otherwise
    -> human review
```

These thresholds are starting assumptions and must be configurable.

### Important

Routing must also escalate cases with:

- schema validation failure
- contradictory output
- unsupported taxonomy values
- empty/meaningless comments
- comments containing multiple incompatible reasons where a single label would be misleading

---

## 14. Model Strategy

The brief requires at least two different models and a cost/latency/quality justification.

The implementation must use LangChain-compatible chat model integrations.

### 14.1 Model A

Purpose:

- bulk classification
- low cost
- low latency

Used for:

- first-pass primary reason classification
- straightforward attribute extraction

### 14.2 Model B

Purpose:

- higher-quality reasoning on difficult cases

Used only for:

- low-confidence Model A outputs
- ambiguous Hinglish
- mixed/multi-issue comments
- difficult attribute extraction
- structurally valid but semantically uncertain Model A outputs

### 14.3 Provider interchangeability

Model A and Model B must be configurable independently.

Examples:

```text
MODEL_A_PROVIDER=openai
MODEL_A_NAME=<cheap-model>

MODEL_B_PROVIDER=anthropic
MODEL_B_NAME=<strong-model>
```

or:

```text
MODEL_A_PROVIDER=google
MODEL_A_NAME=<cheap-model>

MODEL_B_PROVIDER=openai
MODEL_B_NAME=<strong-model>
```

The rest of the application must not depend on a specific provider.

Create a model factory or adapter layer that returns LangChain chat-model instances.

Conceptual example:

```python
def get_model(provider: str, model_name: str, temperature: float):
    ...
```

### 14.4 Structured output

Use LangChain structured output with Pydantic.

Preferred shape:

```python
structured_model = model.with_structured_output(ReturnClassification)
```

Do not make free-form model text the contract between workflow stages.

### 14.5 Quality escalation vs technical fallback

These are two different concepts and must be implemented separately.

#### Quality escalation

Business decision:

```text
Model A returns low confidence or ambiguous classification
-> send to Model B
```

This is explicit routing logic.

#### Technical fallback

Infrastructure resilience:

```text
Model A provider errors / times out / is temporarily unavailable
-> fallback to an alternate model
```

Where useful, use LangChain fallback composition for this.

Do not treat a technical fallback as a substitute for quality escalation.

### 14.6 Engineering requirement

Model providers and specific model IDs must be configurable through environment variables or a settings module.

Do not hardcode secrets.

```text
MODEL_A_PROVIDER=
MODEL_A_NAME=
MODEL_A_TEMPERATURE=0.0

MODEL_B_PROVIDER=
MODEL_B_NAME=
MODEL_B_TEMPERATURE=0.0
```

## 15. Temperature Requirements

Temperatures must be explicitly configured and documented.

Recommended defaults:

```text
Classification: 0.0
Extraction:     0.0
Evaluation:     0.0
```

This MVP does not require creative customer-facing generation.

If any non-zero temperature is used, the reason must be documented.

---

## 16. Deterministic Code vs Model Calls

The implementation must make the boundary explicit.

### Use deterministic code for

- CSV reading
- schema validation
- null checks
- data typing
- filtering
- counting
- percentages
- grouping
- aggregation
- sorting
- threshold comparison
- routing logic
- cost arithmetic
- evaluation metrics
- dashboard charts
- export generation

### Use models for

- interpreting messy language
- understanding Hinglish
- mapping free text into taxonomy
- resolving linguistic ambiguity
- extracting semantic attributes
- difficult judgment calls

No model should be used to calculate counts or percentages.

---

## 17. Confidence and Human Review

The system must never silently force an ambiguous comment into a category.

Example comments that should likely require review:

```text
not good
fit nahi
different
acha nahi
problem hai
return karna hai
```

Human review is a core feature, not an error condition.

### Required review reasons

Store a review reason such as:

```text
LOW_CONFIDENCE
AMBIGUOUS_TEXT
MULTIPLE_REASONS
SCHEMA_FAILURE
NO_USEFUL_TEXT
MODEL_DISAGREEMENT
UNSUPPORTED_OUTPUT
```

---

## 18. Dashboard Requirements

The dashboard should provide useful decision support, not merely model metrics.

### 18.1 Overview

Display:

- total returns loaded
- total `Other`
- % `Other`
- successfully classified
- escalated to Model B
- sent to human review

### 18.2 Return reason distribution

Show:

- original dropdown distribution
- decomposed `"Other"` distribution
- final structured return distribution

### 18.3 SKU intelligence

Show top SKUs by:

- total classified returns
- fit complaints
- too-small complaints
- too-large complaints
- quality complaints
- appearance complaints

Allow selection of a SKU.

For the selected SKU show:

- reason breakdown
- fit sub-reason breakdown
- body-area breakdown
- source comments

### 18.4 Vendor intelligence

Show vendors with high concentrations of:

- quality/fabric complaints
- defects
- appearance mismatch
- fit complaints

Important: use counts and rates carefully.

Because the MVP dataset contains returns only and not all units sold, do **not** label a metric as a true vendor return rate unless a denominator exists.

Prefer wording such as:

> "Share of classified return records associated with this vendor"

### 18.5 Category intelligence

Show reason distribution by:

- Womenswear
- Kidswear
- Mens Basics

### 18.6 Drill-down

Every aggregate insight should allow the user to inspect:

- original comments
- model classifications
- confidence
- review status

---

## 19. Planted Demo Patterns

The code must not hardcode these findings.

They exist only so a working system has meaningful patterns to discover.

Expected examples:

### KRT-184

The dataset contains a concentrated:

```text
fit
 -> too_small
    -> chest
```

pattern.

The dashboard should surface this through normal aggregation.

### Vendor_12

The dataset contains an elevated number of:

```text
quality_issue
 -> fabric_quality / material_mismatch / comfort
```

records.

The dashboard should make this visible without special-case code.

---

## 20. Evaluation Requirements

Use the hidden `expected_*` fields only after inference.

### Required metrics

At minimum calculate:

- primary reason accuracy
- sub-reason accuracy
- body-area accuracy where applicable
- percentage auto-accepted by Model A
- percentage escalated to Model B
- percentage sent to human review
- accuracy of Model A auto-accepted cases
- accuracy after Model B
- final automated accuracy excluding human-review cases
- schema validation failure rate

### Useful confusion analysis

Generate a confusion matrix or equivalent table for primary reason.

Specifically inspect:

- `fit` vs `product_not_as_expected`
- `quality_issue` vs `product_not_as_expected`
- `appearance_issue` vs `product_not_as_expected`
- `changed_mind` vs `unclear`

### Evaluation principle

A desirable system may prefer:

```text
high precision on auto-accepted cases
+
visible human review for uncertain cases
```

over maximizing automation rate.

Do not optimize purely for "% automated".

---

## 21. LangSmith Observability

LangSmith is **recommended but not mandatory** for the MVP.

If enabled, tracing should capture:

- chain inputs
- prompt versions
- model selected
- Model A vs Model B path
- latency
- token usage
- provider/model errors
- schema validation failures
- fallback behavior
- routing outcome
- human-review outcome where practical

Useful demonstration trace:

```text
Input: "not good"
   |
   v
Model A
confidence = 0.42
   |
   v
Quality router
   |
   v
Model B
confidence = 0.55
   |
   v
Human review
```

If LangSmith is not configured, the application must still expose enough local logs/metrics to understand:

- which model handled each record
- why escalation occurred
- which calls failed
- token/cost usage where available

LangSmith credentials must be optional and provided via environment variables.

---

## 22. Cost Requirements

The application must calculate model cost deterministically.

Track:

- Model A input tokens
- Model A output tokens
- Model B input tokens
- Model B output tokens
- cost per row
- total run cost
- cost per 1,000 return comments
- percentage escalated to Model B

If provider usage metadata is unavailable, calculate an estimate from known token counts and configured price assumptions.

The UI should clearly label estimated vs measured cost.

---

## 23. Latency Requirements

Track:

- total processing time
- average latency per Model A call
- average latency per Model B call
- end-to-end batch duration

For the MVP, correctness and visible progress are more important than aggressive optimization.

Where supported, batch or parallelize independent records with a safe concurrency limit.

If parallelization is introduced, it should be documented as a deliberate workflow pattern rather than incidental implementation.

---

## 24. Error and Failure Handling

Failures must be visible.

Never silently drop a record.

Each row should finish in one of these states:

```text
CLASSIFIED_MODEL_A
CLASSIFIED_MODEL_B
NEEDS_HUMAN_REVIEW
PROCESSING_ERROR
INVALID_INPUT
```

### Schema failure behavior

If a model returns invalid output:

1. retry once with a schema-repair instruction or native structured-output mechanism
2. validate again
3. if still invalid:
   - escalate to Model B if it originated from Model A
   - otherwise route to human review / visible failure

Do not regex-parse arbitrary free text as the primary interface between model steps.

---

## 25. Frontend Requirements

Recommended technology:

**Streamlit**

Alternative:

**Gradio**

Required qualities:

- usable without developer narration
- visible upload state
- visible processing state
- visible failures
- clear insight navigation
- usable at the deployed URL
- no notebook dependency

Suggested navigation:

```text
Overview
Upload & Process
Insights
Review Queue
Evaluation
Run Cost
```

---

## 26. Deployment Requirements

The MVP must:

- be deployed to a public or shareable URL
- work from a fresh browser session
- not depend on a local notebook
- keep all application code in the repository
- run locally from documented commands

Suitable MVP platforms include:

- Streamlit Community Cloud
- Hugging Face Spaces
- Render
- Railway
- another simple hosted app platform

Do not spend project time on production infrastructure.

---

## 27. Local Developer Experience

A new developer should be able to run the project in approximately five minutes.

Expected workflow:

```bash
git clone <repo>
cd <repo>
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# add model API keys
streamlit run app.py
```

Windows instructions may be added separately.

---

## 28. Suggested Repository Structure

```text
dhaga-return-intelligence/
|
|-- app.py
|-- requirements.txt
|-- README.md
|-- .env.example
|-- .gitignore
|
|-- data/
|   |-- dhaga_returns_intelligence_synthetic_1000.csv
|
|-- src/
|   |-- __init__.py
|   |-- config.py
|   |-- schemas.py
|   |
|   |-- models/
|   |   |-- __init__.py
|   |   |-- model_factory.py
|   |   |-- provider_config.py
|   |
|   |-- prompts/
|   |   |-- __init__.py
|   |   |-- classification_prompts.py
|   |   |-- extraction_prompts.py
|   |
|   |-- chains/
|   |   |-- __init__.py
|   |   |-- primary_classifier.py
|   |   |-- attribute_extractor.py
|   |   |-- strong_classifier.py
|   |
|   |-- routing/
|   |   |-- __init__.py
|   |   |-- confidence_router.py
|   |   |-- fallback_policy.py
|   |
|   |-- analytics.py
|   |-- evaluator.py
|   |-- costing.py
|   |-- storage.py
|   |-- tracing.py
|
|-- tests/
|   |-- test_schema.py
|   |-- test_chains.py
|   |-- test_router.py
|   |-- test_fallbacks.py
|   |-- test_analytics.py
|   |-- test_evaluation.py
|
|-- docs/
|   |-- discovery_note.md
|   |-- build_note.md
|   |-- requirements.md
|
|-- output/
    |-- .gitkeep
```

### Required LangChain dependencies

Use only the provider integrations actually needed.

Likely dependencies:

```text
langchain
langchain-core
pydantic
pandas
streamlit
```

Plus one or more provider-specific packages, for example:

```text
langchain-openai
langchain-anthropic
langchain-google-genai
```

If LangSmith is used:

```text
langsmith
```

Avoid installing unused provider packages.

## 29. Recommended Internal Result Schema

Store a normalized result for each processed record.

Example:

```json
{
  "return_id": "R0001",
  "sku": "KRT-184",
  "original_dropdown": "Other",
  "original_text": "chest se tight hai",
  "primary_reason": "fit",
  "sub_reason": "too_small",
  "body_area": "chest",
  "confidence": 0.93,
  "classifier_model": "model-a",
  "escalated": false,
  "needs_review": false,
  "review_reason": null,
  "evidence_text": "chest se tight hai",
  "status": "CLASSIFIED_MODEL_A"
}
```

---

## 30. State / Persistence

For the MVP, production persistence is not required.

Acceptable options:

- Streamlit session state
- pandas DataFrame in memory
- local SQLite
- local JSON/CSV output

Recommended:

**SQLite or in-memory DataFrame plus downloadable CSV.**

The user should be able to export the final classified dataset.

---

## 31. Security and Privacy

The provided MVP dataset is synthetic.

Still:

- API keys must live in environment variables or platform secrets.
- Never print secrets in logs.
- Do not commit `.env`.
- Do not send evaluation-only fields to the models.
- Avoid logging full customer comments unnecessarily.
- Clearly state that a production version would require data-retention and PII review before real return records are processed.

---

## 32. Acceptance Criteria

The MVP is considered complete when all of the following are true:

### Input

- [ ] User can upload the provided 1,000-row CSV.
- [ ] Application validates the required columns.
- [ ] Application shows exactly 440 `"Other"` records for the provided dataset.
- [ ] Ground-truth columns are excluded from model input.

### Classification

- [ ] All eligible `"Other"` comments are processed or visibly fail.
- [ ] Every successful model call returns validated structured output.
- [ ] At least two distinct models are used.
- [ ] Model A handles the bulk path.
- [ ] Low-confidence/ambiguous cases can route to Model B.
- [ ] Unresolved cases enter human review.
- [ ] No unsupported label can silently enter the dataset.

### Workflow patterns

- [ ] LangChain is used as the orchestration layer.
- [ ] Prompt templates are implemented with LangChain.
- [ ] Structured outputs use LangChain + Pydantic.
- [ ] Prompt chaining is implemented deliberately.
- [ ] Routing is implemented deliberately.
- [ ] Model A and Model B can be swapped independently through configuration.
- [ ] Quality escalation and technical fallback are implemented as separate concepts.
- [ ] The workflow does not use a LangChain agent.
- [ ] The team can explain what breaks or degrades if each pattern is removed.
- [ ] If LangSmith is enabled, representative traces can be shown during debugging/demo.

### Insights

- [ ] Dashboard shows decomposed `"Other"` reasons.
- [ ] Dashboard shows SKU-level patterns.
- [ ] Dashboard shows vendor-level patterns.
- [ ] Dashboard shows category-level patterns.
- [ ] User can inspect original comments behind an aggregate.
- [ ] `KRT-184` fit/chest pattern is discoverable through normal analysis.
- [ ] `Vendor_12` quality/fabric pattern is discoverable through normal analysis.

### Review

- [ ] Ambiguous comments can be reviewed manually.
- [ ] Reviewer can change classification.
- [ ] Reviewed result updates downstream analytics.

### Evaluation

- [ ] Primary reason accuracy is calculated.
- [ ] Sub-reason accuracy is calculated.
- [ ] Body-area accuracy is calculated where applicable.
- [ ] Auto-accept rate is calculated.
- [ ] Escalation rate is calculated.
- [ ] Human-review rate is calculated.
- [ ] Accuracy of auto-accepted cases is calculated.

### Cost / operations

- [ ] Total run cost or cost estimate is displayed.
- [ ] Cost per 1,000 comments is displayed.
- [ ] Model A vs Model B usage is visible.
- [ ] Processing failures are visible.
- [ ] Temperatures are explicitly configured.
- [ ] README explains code vs model responsibilities.
- [ ] Fresh local setup works from README instructions.
- [ ] Application is deployed to a URL.

---

## 33. Demo Scenario

Use the following presentation path.

### Step 1 — Show the problem

Upload the dataset and show:

```text
1,000 return records
440 classified as "Other"
44% of all sample returns provide no useful structured reason
```

### Step 2 — Run intelligence pipeline

Show:

```text
Model A processing
Model B escalations
Human-review cases
```

### Step 3 — Show "Other" decomposed

Demonstrate that `"Other"` now becomes meaningful categories such as:

```text
Fit
Quality / fabric
Appearance / colour
Wrong / damaged
Changed mind
Delivery
Product not as expected
Unclear
```

### Step 4 — Surface a product issue

Select `KRT-184`.

Show the concentration of:

```text
Fit
 -> Too small
    -> Chest
```

Open several original customer comments.

### Step 5 — Surface a vendor issue

Show the higher concentration of fabric/quality complaints associated with `Vendor_12`.

Do not describe this as a true vendor return rate because sales denominators are not available.

### Step 6 — Show a failure case

Open an ambiguous comment such as:

```text
"not good"
```

Demonstrate:

```text
Model A uncertain
 -> Model B
 -> still uncertain
 -> Human review
```

This failure case is intentional and must be part of the live demo.

### Step 7 — Show evaluation and cost

Finish with:

- classification quality
- auto-accept accuracy
- review rate
- Model B escalation rate
- total run cost
- estimated cost at larger volume

---

## 34. Engineering Priorities

Build in this order:

### P0 — Required

1. CSV validation
2. Pydantic schemas
3. LangChain model factory / provider configuration
4. LangChain prompt templates
5. Model A structured classification chain
6. chained attribute extraction
7. explicit confidence-based routing
8. Model B quality escalation
9. technical fallback behavior
10. human-review status
11. deterministic analytics
12. Streamlit dashboard
13. evaluation
14. cost tracking
15. deployment

### P1 — Useful if time allows

- editable review queue
- result export
- caching
- concurrency
- confusion matrix
- prompt version logging
- run history

### P2 — Explicitly defer

- production integrations
- user authentication
- sophisticated RBAC
- vector database
- autonomous agents
- vendor alerts
- automated catalogue changes
- return prediction
- customer-facing bot

---

## 35. Implementation Principle

The MVP should optimize for:

> **Smallest honest system that demonstrates the business value end-to-end.**

LangChain is an implementation choice, not the product.

The product is **not the classifier**, the chain, or the framework.

The product is the ability for the Category Head to move from:

> `"Other" = 44%`

to:

> **"These SKUs and vendors have these recurring customer-reported issues, here is the evidence, and here are the cases the system is not confident enough to decide."**

That is the behavior the implementation should be designed around.


---

## 36. Coding Agent Implementation Summary

The coding agent should implement the MVP with the following principles:

```text
Streamlit
   |
   v
LangChain orchestration
   |
   +--> PromptTemplate / ChatPromptTemplate
   |
   +--> Model A (cheap / fast)
   |      |
   |      v
   |   Pydantic structured output
   |
   +--> explicit confidence router
           |
           +--> accept
           |
           +--> Model B (stronger / possibly different provider)
                    |
                    v
                 Pydantic structured output
                    |
                    +--> accept
                    |
                    +--> human review
   |
   v
Python / pandas analytics
   |
   v
Dashboard
```

### Required implementation choices

- Use LangChain.
- Use direct, explicit chains rather than an agent.
- Use Pydantic-backed structured output.
- Keep Model A and Model B provider-agnostic.
- Keep routing logic explicit.
- Separate quality escalation from technical fallback.
- Keep arithmetic and analytics deterministic.
- Make failure states visible.
- Keep LangSmith optional but easy to enable.
- Keep the code simple enough that every step can be explained during the client presentation.
