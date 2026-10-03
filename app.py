from functools import partial
from pathlib import Path
import time
import pandas as pd
import altair as alt
import streamlit as st

from src.analytics import accepted, distribution, final_frame, findings, intelligence
from src.config import Settings
from src.evaluator import evaluate
from src.ingestion import read_upload, validate_data, split_data, is_other
from src.pipeline import Pipeline
from src.models import get_model
from src.schemas import TAXONOMY, BODY_AREAS
from src.storage import review_result, csv_export, json_export

ROOT = Path(__file__).parent
SAMPLE = ROOT / "data" / "dhaga_returns_intelligence_synthetic_1000.csv"
st.set_page_config(page_title="Dhaga & Co. | Return intelligence", page_icon="🧵", layout="wide")
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Libre+Caslon+Display&display=swap');
html,body,[class*="css"],.stApp{font-family:'DM Sans',sans-serif}
.block-container{padding-top:2.7rem;max-width:1440px;padding-bottom:4rem}
h1{font-family:'Libre Caslon Display',Georgia,serif!important;font-size:3.55rem!important;line-height:1.08!important;font-weight:400!important;letter-spacing:-1.8px}
h2{font-family:'Libre Caslon Display',Georgia,serif!important;font-size:2.1rem!important;font-weight:400!important}
h3{font-size:1.15rem!important;font-weight:600!important}
[data-testid="stSidebar"]{background:#243D34}
[data-testid="stSidebar"] *{color:#F5F1E9}
[data-testid="stSidebar"] [data-testid="stRadio"] label{padding:.38rem 0}
[data-testid="stSidebar"] hr{border-color:#ffffff25}
[data-testid="stMetric"]{background:#FFFFFF99;border:1px solid #DEDCD4;border-radius:8px;padding:1.05rem 1.2rem}
[data-testid="stMetricLabel"]{color:#647068;font-size:.82rem}
[data-testid="stMetricValue"]{font-family:Georgia,serif;font-size:2.15rem;color:#243D34}
.eyebrow{font-size:.73rem;letter-spacing:2px;text-transform:uppercase;color:#8C5140;font-weight:700;margin-bottom:1rem}
.lead{font-size:1.05rem;max-width:750px;line-height:1.7;color:#647068;margin-bottom:1.5rem}
.brand{font-family:Georgia,serif;font-size:2rem;margin:.5rem 0 0}
.brand-sub{font-size:.65rem;letter-spacing:2.3px;margin-bottom:2.6rem;opacity:.7}
.hero{border-left:3px solid #AC6147;padding-left:1.4rem;margin:1.5rem 0}
.stButton button{border-radius:5px;padding:.55rem 1.15rem}
.stDataFrame{border-radius:7px;overflow:hidden}
footer{visibility:hidden}
</style>""", unsafe_allow_html=True)


def clear_api_key():
    st.session_state.pop("personal_openai_key", None)


def load_frame(frame, name):
    st.session_state.raw = frame
    st.session_state.errors = validate_data(frame)
    st.session_state.source, st.session_state.labels = split_data(frame)
    st.session_state.source_name = name
    st.session_state.results = []
    st.session_state.events = []
    st.session_state.run_meta = {}


if "source" not in st.session_state:
    load_frame(read_upload(SAMPLE.read_bytes(), SAMPLE.name), "Supplied synthetic dataset")


def heading(kicker, title, detail):
    st.markdown(f'<div class="eyebrow">{kicker}</div>', unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<div class="lead">{detail}</div>', unsafe_allow_html=True)


def metrics(items):
    cols = st.columns(len(items))
    for col, (label, value) in zip(cols, items):
        col.metric(label, value)


def chart(frame, column, color="#385D4C"):
    counts = distribution(frame, column)
    if counts.empty:
        st.info("No matching records yet.")
        return
    counts["label"] = counts[column].astype(str).str.replace("_", " ").str.capitalize()
    bars = alt.Chart(counts).mark_bar(color=color, cornerRadiusEnd=3).encode(
        x=alt.X("returns:Q", title="Return records", axis=alt.Axis(tickMinStep=1)),
        y=alt.Y("label:N", sort="-x", title=None, axis=alt.Axis(labelLimit=230, labelOverlap=False)),
        tooltip=[alt.Tooltip("label:N", title="Reason"), "returns:Q"]
    ).properties(height=max(130, len(counts) * 32))
    st.altair_chart(bars, use_container_width=True)


def evidence_table(frame, key="evidence"):
    cols = ["return_id", "sku", "product_name", "category", "vendor", "return_reason_dropdown", "return_reason_text",
            "primary_reason", "sub_reason", "body_area", "confidence", "status", "review_reason"]
    st.dataframe(frame[[c for c in cols if c in frame.columns]], hide_index=True, use_container_width=True,
                 column_config={"return_reason_text": st.column_config.TextColumn("Customer comment", width="large"),
                                "confidence": st.column_config.NumberColumn("Model confidence", format="%.2f")}, key=key)


with st.sidebar:
    st.markdown('<div class="brand">dhaga & co.</div><div class="brand-sub">RETURN INTELLIGENCE</div>', unsafe_allow_html=True)
    page = st.radio("Workspace", ["Overview", "Upload & Process", "Insights", "Review Queue", "Evaluation", "Run Cost"], label_visibility="collapsed")
    st.divider()
    st.caption("WORKSPACE")
    st.write("Neha · Category Head")
    st.caption("Synthetic-data MVP")
    st.caption("Session-only storage. Download results before closing this tab.")
    if st.session_state.run_meta:
        st.divider()
        st.caption("CURRENT RUN")
        st.write("Offline demonstration" if st.session_state.run_meta.get("demo") else "Live model run")
        st.caption(f'{len(st.session_state.results):,} comments processed')

source = st.session_state.source
results = st.session_state.results
errors = st.session_state.errors
frame = final_frame(source, results)
other_count = int(is_other(source).sum()) if "return_reason_dropdown" in source else 0
pending = sum(r["needs_review"] for r in results)
resolved = sum(not r["needs_review"] and r["primary_reason"] != "unclear" for r in results)

if st.session_state.run_meta.get("demo"):
    st.caption("OFFLINE DEMO · Deterministic keyword rules. No model calls or API charges. Metrics do not measure LLM quality.")
if errors:
    st.error("This dataset cannot be processed. Open Upload & Process to see validation errors and replace it.")

if page == "Overview":
    heading("Category workspace / overview", "Every return tells a story.",
            "Find recurring product issues, inspect the customer evidence, and give uncertain cases a human decision.")
    metrics([("Returns loaded", f"{len(source):,}"), ("Filed under ‘Other’", f"{other_count:,}"),
             ("Other share of sample", f"{other_count / len(source):.0%}" if len(source) else "—"),
             ("Awaiting human review", f"{pending:,}")])
    st.markdown("<div class='hero'><strong>From return reasons to investigation priorities.</strong><br>"
                "Start with the supplied sample in Upload & Process. Then explore the patterns and their original comments.</div>", unsafe_allow_html=True)
    left, right = st.columns([1.15, 1], gap="large")
    with left:
        st.subheader("What customers selected")
        chart(source, "return_reason_dropdown")
    with right:
        st.subheader("Your next steps")
        with st.container(border=True):
            st.markdown("**01  Validate your data**")
            st.write("The supplied Excel data is included. You can also upload a CSV or workbook.")
            st.markdown("**02  Process ‘Other’ comments**")
            st.write("Try the offline demo, or select live models once API credentials are configured.")
            st.markdown("**03  Investigate and review**")
            st.write("Explore SKU and vendor patterns. Confirm or correct uncertain records, then export.")
        st.caption("Client brief: overall returns are 31%. This sample contains returned orders only; it cannot establish a sales-based return rate.")
    if results:
        st.subheader("Recurring issues to investigate")
        st.dataframe(findings(frame).head(8), hide_index=True, use_container_width=True)
        st.caption("Ranked by accepted Other-comment count. Open Insights to inspect the evidence.")

elif page == "Upload & Process":
    heading("01 / prepare and classify", "Make ‘Other’ useful.", "Load return records, validate the data, and process the comments with visible progress.")
    upload = st.file_uploader("Upload returns", type=["csv", "xlsx"], help="Excel uses the Returns_Data sheet if present, otherwise the first sheet. Maximum 10 MB and 10,000 rows.")
    col1, col2 = st.columns([1, 3])
    if col1.button("Load supplied sample"):
        load_frame(read_upload(SAMPLE.read_bytes(), SAMPLE.name), "Supplied synthetic dataset")
        st.rerun()
    if upload is not None and col2.button("Validate uploaded file", type="primary"):
        try:
            load_frame(read_upload(upload.getvalue(), upload.name), upload.name)
            st.rerun()
        except Exception as error:
            st.error(f"Cannot read file: {type(error).__name__}. Check the format and workbook sheet.")
            st.stop()
    st.caption(f"Current source: {st.session_state.source_name}")
    if errors:
        for error in errors:
            st.error(error)
        st.dataframe(st.session_state.raw.head(25), hide_index=True)
        st.stop()
    metrics([("Rows", len(source)), ("Other", other_count), ("SKUs", source.sku.nunique()),
             ("Categories", source.category.nunique()), ("Vendors", source.vendor.nunique())])
    st.success("Validation passed. Required fields, unique return IDs, dates, and Other comments are present.")
    with st.expander("Inspect original records"):
        st.dataframe(source, hide_index=True, use_container_width=True)
        st.caption("Evaluation labels are held separately and are never available to the model input builder.")
    st.divider()
    mode = st.radio("Processing mode", ["Offline demo", "Live models"], horizontal=True)
    settings = Settings()
    with st.expander("Model routing and run settings"):
        st.write(f"Model A: {settings.model_a.identity} · Model B: {settings.model_b.identity}")
        st.caption("Model A performs classification, then attribute extraction. Model B re-evaluates uncertain cases.")
        settings.threshold_a = st.slider("Model A acceptance threshold", 0.0, 1.0, settings.threshold_a, 0.01)
        settings.threshold_b = st.slider("Model B acceptance threshold", 0.0, 1.0, settings.threshold_b, 0.01)
        st.caption("Confidence values are model-provided routing signals, not calibrated probabilities. Models and prices are configured in .env or host secrets.")
    model_factory = get_model
    credentials_ready = True
    if mode == "Live models":
        credential_source = st.radio("API credentials", ["Use my OpenAI API key", "Use server credentials"])
        st.info("Live processing sends return comments to the configured providers and incurs API charges. If enabled by the host, LangSmith tracing also receives comments and model outputs.")
        if credential_source == "Use my OpenAI API key":
            personal_key = st.text_input("OpenAI API key", type="password", key="personal_openai_key",
                help="Sent securely to this app's server on HTTPS deployments, then used to authenticate OpenAI calls. Only use a deployment you trust.").strip()
            st.button("Clear API key", on_click=clear_api_key)
            st.caption("Your key is held in this session's memory, not written to disk or included in result exports. It overrides the server's OpenAI key for this run. Charges apply to your OpenAI account; ChatGPT subscriptions do not include API credits. Clear the key when finished.")
            configs = [settings.model_a, settings.model_b, settings.fallback]
            compatible = all(cfg.provider == "openai" for cfg in configs if cfg)
            if not compatible:
                st.error("Personal OpenAI keys require Model A, Model B, and any enabled fallback to use the OpenAI provider. Ask the host to update the configuration.")
            credentials_ready = bool(personal_key) and compatible
            model_factory = partial(get_model, openai_api_key=personal_key)
        else:
            clear_api_key()
            st.caption("Uses credentials configured by the host. The host's provider account is billed.")
    else:
        clear_api_key()
    if results:
        st.success(f"{len(results):,} of {other_count:,} Other comments processed. Open Insights or Review Queue.")
        with st.expander("Start another run"):
            st.caption("This clears this session’s current results and review corrections. Export them first from Insights.")
            if st.button("Clear results for a new run"):
                st.session_state.results = []
                st.session_state.events = []
                st.session_state.run_meta = {}
                st.rerun()
    if st.button("Run classification", type="primary", disabled=bool(results) or other_count == 0 or not credentials_ready):
        try:
            pipeline = Pipeline(settings, demo=mode == "Offline demo", model_factory=model_factory)
            pipeline.preflight()
        except Exception as error:
            st.error(f"Model setup failed ({type(error).__name__}). Check provider integration, model names and the selected API credentials. No rows were processed.")
            st.stop()
        start = time.perf_counter()
        bar = st.progress(0.0, text="Preparing comments…")
        live = st.empty()
        st.session_state.run_meta = {"demo": pipeline.demo, "run_id": pipeline.run_id,
            "threshold_a": settings.threshold_a, "threshold_b": settings.threshold_b,
            "model_a": settings.model_a.identity, "model_b": settings.model_b.identity,
            "temperature_a": settings.model_a.temperature, "temperature_b": settings.model_b.temperature}
        for i, row in enumerate(source[is_other(source)].to_dict("records"), 1):
            st.session_state.results.append(pipeline.process(row))
            st.session_state.events = pipeline.events
            current = st.session_state.results
            known_cost = all(e["cost_usd"] is not None for e in pipeline.events)
            cost_text = f'${sum(e["cost_usd"] for e in pipeline.events):.4f}' if known_cost else "unavailable"
            bar.progress(i / other_count, text=f"{i:,} / {other_count:,} comments processed")
            live.caption(f'Model A accepted: {sum(r["status"] == "CLASSIFIED_MODEL_A" for r in current)} · '
                         f'Escalated: {sum(r["escalated"] for r in current)} · '
                         f'Review: {sum(r["needs_review"] for r in current)} · '
                         f'Schema failures: {sum(r["schema_failures"] for r in current)} · '
                         f'Call errors: {sum(r["processing_errors"] for r in current)} · '
                         f'Estimated cost: {cost_text} · Elapsed: {time.perf_counter() - start:.1f}s')
        st.session_state.run_meta["duration_seconds"] = time.perf_counter() - start
        st.rerun()

elif page == "Insights":
    heading("02 / investigate", "Follow the evidence.", "Explore customer-reported issues by product, vendor, and category. Every filter leads back to the original return comment.")
    if not results:
        st.info("Run classification in Upload & Process to unlock the insights.")
        st.stop()
    metrics([("Other comments processed", f"{len(results):,}"), ("Resolved with a reason", f"{resolved / len(results):.1%}"),
             ("Currently awaiting review", f"{pending / len(results):.1%}"),
             ("Escalated to Model B", f'{sum(r["escalated"] for r in results) / len(results):.1%}')])
    st.caption("Unresolved predictions are excluded from accepted issue counts. Confirmed unclear records stay visible as unclear.")
    tab1, tab2, tab3, tab4 = st.tabs(["Reason landscape", "Products", "Vendors", "Categories"])
    with tab1:
        left, right = st.columns(2, gap="large")
        other = frame[is_other(frame)].copy()
        other["display_reason"] = other.apply(lambda r: "awaiting_review" if r.needs_review else r.primary_reason, axis=1)
        with left:
            st.subheader("‘Other’, decomposed")
            chart(other, "display_reason")
        with right:
            st.subheader("Final return landscape")
            landscape = frame.copy()
            landscape["display_reason"] = landscape.apply(lambda r: "awaiting_review" if r.needs_review else r.primary_reason, axis=1)
            chart(landscape, "display_reason", "#AF7654")
            st.caption("Combines existing structured dropdowns with classified Other comments.")
        fit = accepted(other)
        fit = fit[fit.primary_reason.eq("fit")]
        left, right = st.columns(2)
        with left:
            st.subheader("Fit direction")
            chart(fit, "sub_reason")
        with right:
            st.subheader("Where the fit issue occurs")
            chart(fit, "body_area", "#AF7654")
    for tab, dimension, title in [(tab2, "sku", "Products"), (tab3, "vendor", "Vendors"), (tab4, "category", "Categories")]:
        with tab:
            st.subheader(title + " by classified return count")
            scope = st.radio("Records to include", ["Classified Other comments", "All return records"], horizontal=True, key=dimension + "_scope")
            subset = frame[is_other(frame)] if scope.startswith("Classified") else frame
            table = intelligence(subset, dimension)
            if not table.empty:
                sort = st.selectbox("Rank by", ["classified_returns", "fit", "too_small", "too_large", "quality", "appearance", "defects", "quality_share_pct"], key=dimension + "_sort")
                st.dataframe(table.sort_values(sort, ascending=False), hide_index=True, use_container_width=True)
                st.caption("Quality share = quality complaints ÷ classified return records in this group. This is not a vendor or product return rate.")
            choice = st.selectbox(f"Inspect a {dimension}", sorted(subset[dimension].unique()), key=dimension + "_choice")
            selected = subset[subset[dimension].eq(choice)]
            left, right = st.columns(2)
            with left:
                chart(accepted(selected), "primary_reason")
            with right:
                selected_fit = accepted(selected)
                selected_fit = selected_fit[selected_fit.primary_reason.eq("fit")]
                chart(selected_fit, "body_area", "#AF7654")
                chart(selected_fit, "sub_reason")
            evidence_table(selected, dimension + "_evidence")
    st.divider()
    st.subheader("Explore source comments")
    c1, c2, c3 = st.columns(3)
    reason = c1.selectbox("Primary reason", ["All"] + sorted(frame.primary_reason.unique()))
    sub = c2.selectbox("Sub-reason", ["All"] + sorted(set(frame.sub_reason) - {""}))
    body = c3.selectbox("Body area", ["All"] + BODY_AREAS)
    c1, c2 = st.columns(2)
    state = c1.selectbox("Review status", ["All", "Awaiting review", "Human reviewed", "Accepted automatically"])
    search = c2.text_input("Search comments or return IDs")
    filtered = frame.copy()
    for column, value in [("primary_reason", reason), ("sub_reason", sub), ("body_area", body)]:
        if value != "All":
            filtered = filtered[filtered[column].eq(value)]
    if state == "Awaiting review":
        filtered = filtered[filtered.needs_review]
    elif state == "Human reviewed":
        filtered = filtered[filtered.reviewed]
    elif state == "Accepted automatically":
        filtered = filtered[filtered.status.isin(["CLASSIFIED_MODEL_A", "CLASSIFIED_MODEL_B"])]
    if search:
        filtered = filtered[filtered.return_reason_text.str.contains(search, case=False, regex=False) | filtered.return_id.str.contains(search, case=False, regex=False)]
    st.caption(f"{len(filtered):,} matching return records")
    evidence_table(filtered)
    if not filtered.empty:
        inspect_id = st.selectbox("Inspect model decisions for a return", filtered.return_id.tolist())
        decision = next((r for r in results if r["return_id"] == inspect_id), None)
        if decision:
            with st.expander("Model predictions and audit trail"):
                st.json({k: decision.get(k) for k in ["model_a_primary", "model_a_prediction", "model_b_prediction", "escalation_reason", "review_reason", "review_history"]})
        else:
            st.caption("This record retains its original structured dropdown; it was not sent to a model.")
    c1, c2 = st.columns(2)
    c1.download_button("Export final dataset (CSV)", csv_export(frame), "dhaga_classified_returns.csv", "text/csv")
    c2.download_button("Export run and review audit (JSON)", json_export(source, results, st.session_state.events, st.session_state.run_meta), "dhaga_run.json", "application/json")

elif page == "Review Queue":
    heading("03 / human review", "Make the uncertain explicit.", "Review the original comment alongside both predictions. Your decisions update the dashboard while preserving the model’s original output.")
    if not results:
        st.info("Process the data first to populate the review queue.")
        st.stop()
    show_reviewed = st.checkbox("Include previously reviewed records")
    queue = [r for r in results if r["needs_review"] or (show_reviewed and r["reviewed"])]
    metrics([("Awaiting review", pending), ("Human reviewed", sum(r["reviewed"] for r in results)),
             ("Processing failures", sum(r["automated_status"] == "PROCESSING_ERROR" for r in results))])
    if not queue:
        st.success("No records awaiting review.")
        st.stop()
    selected = st.selectbox("Choose a return", [r["return_id"] for r in queue])
    record = next(r for r in queue if r["return_id"] == selected)
    left, right = st.columns([1.15, 1], gap="large")
    with left:
        st.subheader(f'{record["sku"]} · {record["product_name"]}')
        st.caption(f'{record["vendor"]} · {record["category"]} · Original dropdown: {record["return_reason_dropdown"]}')
        with st.container(border=True):
            st.write(record["return_reason_text"])
        st.warning("Review reason: " + (record["review_reason"] or "PREVIOUSLY_REVIEWED"))
        st.write(f'Current category: **{record["primary_reason"]} / {record["sub_reason"]}**')
        st.caption(f'Original model confidence: {record["confidence"]:.2f}. Human review does not increase this score.')
        a, b = st.columns(2)
        with a:
            st.caption("MODEL A")
            st.json(record.get("model_a_prediction") or record.get("model_a_primary") or {"result": "No valid output"})
        with b:
            st.caption("MODEL B")
            st.json(record.get("model_b_prediction") or {"result": "Not used or no valid output"})
    with right:
        st.subheader("Your decision")
        primary = st.selectbox("Primary reason", list(TAXONOMY), index=list(TAXONOMY).index(record["primary_reason"]), key=selected + "_primary")
        options = TAXONOMY[primary]
        sub = st.selectbox("Sub-reason", options, index=options.index(record["sub_reason"]) if record["sub_reason"] in options else 0, key=selected + "_" + primary + "_sub")
        bodies = BODY_AREAS if primary == "fit" else ["none"]
        body = st.selectbox("Body area", bodies, index=bodies.index(record["body_area"]) if record["body_area"] in bodies else bodies.index("none"), key=selected + "_" + primary + "_body")
        note = st.text_area("Review note (optional)", key=selected + "_note")
        action = None
        if st.button("Save correction", type="primary"):
            action = "correct"
        if st.button("Confirm current classification"):
            primary, sub, body = record["primary_reason"], record["sub_reason"], record["body_area"]
            action = "confirm"
        if st.button("Mark unclear"):
            primary, sub, body = "unclear", "insufficient_information", "none"
            action = "mark_unclear"
        if action:
            updated = review_result(record, primary, sub, body, action, note)
            st.session_state.results = [updated if r["return_id"] == selected else r for r in results]
            st.rerun()
        if record["review_history"]:
            with st.expander("Previous review decisions"):
                st.json(record["review_history"])

elif page == "Evaluation":
    heading("Quality / evaluation", "Measure quality. Keep the caveats.", "Compare frozen automated predictions with the supplied synthetic labels. Human edits never improve these model scores.")
    if not results:
        st.info("Run classification before evaluating it.")
        st.stop()
    if st.session_state.run_meta.get("demo"):
        st.warning("These scores evaluate offline rules on this sample, not LLM performance or generalization. Run live models for a model-quality evaluation.")
    st.caption("Only processed Other records are evaluated. Missing labels are excluded per metric. Body-area accuracy includes records with a non-none expected area.")
    report, confusion = evaluate(results, st.session_state.labels)
    def percent(name):
        value = report.get(name)
        return f"{value:.1%}" if value is not None else "N/A"
    metrics([("Primary accuracy", percent("primary_reason accuracy")), ("Sub-reason accuracy", percent("sub_reason accuracy")),
             ("Body-area accuracy", percent("body_area accuracy")), ("Auto-accepted accuracy", percent("Final automated accuracy"))])
    st.subheader("Routing and quality measures")
    metric_rows = []
    for name, value in report.items():
        display = "N/A (no eligible labels)" if value is None else (f"{value:.1%}" if isinstance(value, float) else str(value))
        metric_rows.append({"Metric": name, "Value": display})
    st.dataframe(pd.DataFrame(metric_rows), hide_index=True, use_container_width=True)
    st.subheader("Primary reason confusion matrix")
    st.dataframe(confusion, use_container_width=True)
    st.caption("Rows = supplied label. Columns = model prediction, including predictions awaiting review. Inspect fit, quality and appearance versus product-not-as-expected, and changed-mind versus unclear.")
    st.info("Dataset caveat: the supplied sub-label ‘defect’ is evaluated as ‘general_defect’. Other labels are used as supplied, even where the text may support a different interpretation. Ground truth is synthetic and may be noisy.")
    st.download_button("Download evaluation (CSV)", csv_export(pd.DataFrame(metric_rows)), "dhaga_evaluation.csv", "text/csv")

elif page == "Run Cost":
    heading("Operations / run cost", "Know what the run used.", "Inspect model calls, token usage, latency, retries, and technical fallback behavior.")
    if not results:
        st.info("Run classification to see its cost and execution details.")
        st.stop()
    events = pd.DataFrame(st.session_state.events)
    duration = st.session_state.run_meta.get("duration_seconds", 0)
    total_cost = float(events.cost_usd.sum()) if not events.empty and events.cost_usd.notna().all() else None
    cost_label = f"${total_cost:.4f}" if total_cost is not None else "Unavailable"
    metrics([("Run cost estimate", cost_label), ("Per 1,000 comments", f"${total_cost / len(results) * 1000:.4f}" if total_cost is not None else "Unavailable"),
             ("Batch duration", f"{duration:.1f}s"), ("Call attempts", len(events))])
    if st.session_state.run_meta.get("demo"):
        st.info("Offline rules cost $0 in API charges. The timings below are local rule execution, not model latency.")
    else:
        st.caption("Cost uses configured USD token prices and is always an estimate of billing. Token source is provider-reported or estimated (characters ÷ 4). Cached-token discounts are not modeled.")
        if total_cost is None:
            st.warning("Total cost is unavailable: configure all token prices, or inspect failed calls with unknown usage. Unknown usage is not counted as free.")
    if not events.empty:
        st.subheader("Model usage")
        summary = events.groupby(["role", "model"], dropna=False).agg(
            calls=("stage", "size"), input_tokens=("input_tokens", lambda s: s.sum(min_count=1)),
            output_tokens=("output_tokens", lambda s: s.sum(min_count=1)),
            average_latency_seconds=("latency_seconds", "mean"), failures=("outcome", lambda s: int(s.eq("error").sum())),
            schema_failures=("error", lambda s: int(s.eq("SCHEMA_FAILURE").sum())),
            technical_fallback_calls=("technical_fallback", "sum"))
        st.dataframe(summary, use_container_width=True)
        st.caption(f'Schema failure rate per call attempt: {events.error.eq("SCHEMA_FAILURE").mean():.1%}. Failed attempts and retries remain in this log.')
        st.subheader("Per-return cost and latency")
        st.dataframe(pd.DataFrame(results)[["return_id", "cost_usd", "latency_seconds", "schema_failures", "processing_errors", "technical_fallback", "status"]], hide_index=True, use_container_width=True)
        st.subheader("Call log")
        call_id = st.selectbox("Return ID", ["All"] + list(dict.fromkeys(events.return_id)))
        st.dataframe(events if call_id == "All" else events[events.return_id.eq(call_id)], hide_index=True, use_container_width=True)
        st.download_button("Export call log", csv_export(events), "dhaga_calls.csv", "text/csv")
    with st.expander("Run configuration"):
        st.json(st.session_state.run_meta)
