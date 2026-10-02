from copy import deepcopy
from io import BytesIO
from pathlib import Path
import pandas as pd
import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from src.analytics import final_frame, findings, intelligence
from src.config import Settings, ModelConfig
from src.evaluator import evaluate
from src.ingestion import read_upload, validate_data, split_data, model_input, is_other
from src.pipeline import Pipeline
from src.routing import route_reason
from src.schemas import Classification, PrimaryPrediction, Attributes, unclear
from src.storage import review_result, csv_export

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def sample():
    return read_upload((ROOT / "data/dhaga_returns_intelligence_synthetic_1000.csv").read_bytes(), "sample.csv")


@pytest.fixture
def row():
    return dict(return_id="R1", order_id="O1", sku="SKU1", product_name="Kurti", category="Womenswear", vendor="Vendor_01",
                size_ordered="M", return_reason_dropdown="Other", return_reason_text="chest se tight hai", return_date="2026-01-01")


def fit(confidence=0.93):
    return Classification(primary_reason="fit", sub_reason="too_small", body_area="chest", confidence=confidence,
                          needs_review=False, evidence_text="chest se tight hai", explanation="Explicit tightness.")


def test_supplied_workbook_and_csv_match(sample):
    excel = read_upload((ROOT / "data/dhaga_returns_intelligence_synthetic_1000.xlsx").read_bytes(), "sample.xlsx")
    pd.testing.assert_frame_equal(excel, sample)
    assert len(sample) == 1000 and is_other(sample).sum() == 440
    assert validate_data(sample) == []


@pytest.mark.parametrize("change", ["missing_column", "duplicate_id", "empty_other", "bad_date", "empty_sku", "long_text"])
def test_invalid_batches_rejected(sample, change):
    d = sample.copy()
    if change == "missing_column":
        d = d.drop(columns="sku")
    elif change == "duplicate_id":
        d.loc[1, "return_id"] = " " + d.loc[0, "return_id"] + " "
    elif change == "empty_other":
        d.loc[d.index[is_other(d)][0], "return_reason_text"] = "  "
    elif change == "bad_date":
        d.loc[0, "return_date"] = "not-a-date"
    elif change == "empty_sku":
        d.loc[0, "sku"] = " "
    else:
        d.loc[0, "return_reason_text"] = "a" * 4001
    assert validate_data(d)


def test_hidden_labels_and_extra_columns_excluded(sample):
    sample["secret_extra"] = "DO NOT SEND"
    source, labels = split_data(sample)
    assert not any(c.startswith("expected_") for c in source.columns)
    assert "secret_extra" not in source
    assert set(model_input(sample.iloc[0])) == {"text", "dropdown"}
    assert "expected_primary_reason" in labels


def test_schema_rejects_incompatible_taxonomy():
    for patch in [{"sub_reason": "fabric_quality"}, {"primary_reason": "invented"}, {"confidence": 1.01}, {"body_area": "elbow"}]:
        with pytest.raises(ValidationError):
            Classification(**{**fit().model_dump(), **patch})


def test_thresholds_inclusive():
    assert route_reason(fit(0.85), 0.85) is None
    assert route_reason(fit(0.849), 0.85) == "LOW_CONFIDENCE"
    assert route_reason(unclear("not good"), 0.0) == "AMBIGUOUS_TEXT"


class FakeModel:
    def __init__(self, responses, seen):
        self.responses = responses
        self.seen = seen

    def with_structured_output(self, schema, include_raw):
        def invoke(prompt):
            self.seen.append(prompt.to_string())
            output = self.responses.pop(0)
            if isinstance(output, Exception):
                raise output
            if output == "bad":
                return {"parsed": None, "parsing_error": ValueError("bad"), "raw": AIMessage(content="invalid")}
            return {"parsed": output, "parsing_error": None,
                    "raw": AIMessage(content="", usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120})}
        return RunnableLambda(invoke)


def primary(confidence=0.95, reason="fit", review=False):
    return PrimaryPrediction(primary_reason=reason, confidence=confidence, needs_review=review,
                             review_reason="AMBIGUOUS_TEXT" if review else "NONE")


def attributes(confidence=0.93):
    return Attributes(**fit(confidence).model_dump(exclude={"primary_reason"}))


def fake_pipeline(a, b, fallback=None):
    seen = []
    configs = Settings(model_a=ModelConfig("openai", "cheap", 0, 1, 2), model_b=ModelConfig("openai", "strong", 0, 3, 4),
                       fallback=ModelConfig("openai", "backup", 0, 5, 6) if fallback is not None else None)
    models = {"cheap": FakeModel(a, seen), "strong": FakeModel(b, seen), "backup": FakeModel(fallback or [], seen)}
    return Pipeline(configs, demo=False, model_factory=lambda cfg, timeout: models[cfg.name]), seen


def test_live_chain_primary_then_extraction_without_labels(row):
    p, seen = fake_pipeline([primary(), attributes()], [])
    row["expected_primary_reason"] = "HIDDEN_CANARY"
    r = p.process(row)
    assert r["status"] == "CLASSIFIED_MODEL_A"
    assert len(seen) == 2
    assert "Primary reason: fit" in seen[1]
    assert all("HIDDEN_CANARY" not in prompt for prompt in seen)
    assert r["cost_usd"] == pytest.approx(0.00028)


def test_quality_escalation_separate_from_fallback(row):
    p, _ = fake_pipeline([primary(0.7), attributes()], [fit(0.91)])
    r = p.process(row)
    assert r["status"] == "CLASSIFIED_MODEL_B"
    assert r["escalation_reason"] == "LOW_CONFIDENCE"
    assert not r["technical_fallback"]


def test_schema_retry_then_escalation(row):
    p, _ = fake_pipeline(["bad", "bad"], [fit()])
    r = p.process(row)
    assert r["status"] == "CLASSIFIED_MODEL_B" and r["schema_failures"] == 2
    assert len(p.events) == 3 and all(e["input_tokens"] is not None for e in p.events)


def test_schema_retry_recovers(row):
    p, _ = fake_pipeline(["bad", primary(), attributes()], [])
    r = p.process(row)
    assert r["status"] == "CLASSIFIED_MODEL_A" and r["schema_failures"] == 1


def test_technical_fallback_preserves_call_audit(row):
    p, _ = fake_pipeline([TimeoutError(), TimeoutError(), attributes()], [], [primary()])
    r = p.process(row)
    assert r["status"] == "CLASSIFIED_MODEL_A"
    assert r["technical_fallback"] and not r["escalated"]
    assert len(p.events) == 4
    assert r["cost_usd"] is None  # Failed call usage is unknown, never silently free.


def test_both_models_fail_visibly(row):
    p, _ = fake_pipeline([RuntimeError("secret must not be logged")], [RuntimeError("secret must not be logged")])
    r = p.process(row)
    assert r["status"] == "PROCESSING_ERROR" and r["needs_review"]
    assert "secret" not in str(p.events)


def test_fabricated_evidence_retried_then_review(row):
    invented = fit().model_copy(update={"evidence_text": "not in source"})
    p, _ = fake_pipeline(["bad", "bad"], [invented, invented])
    r = p.process(row)
    assert r["status"] == "NEEDS_HUMAN_REVIEW" and r["review_reason"] == "SCHEMA_FAILURE"
    assert r["schema_failures"] == 4


def test_model_disagreement_requires_review(row):
    wrong = Classification(primary_reason="quality_issue", sub_reason="fabric_quality", body_area="none", confidence=0.95,
                           needs_review=False, evidence_text=row["return_reason_text"], explanation="Alternative")
    p, _ = fake_pipeline([primary(0.7), attributes()], [wrong])
    assert p.process(row)["review_reason"] == "MODEL_DISAGREEMENT"


def test_no_useful_text_visible_without_calls(row):
    row["return_reason_text"] = "..."
    p = Pipeline()
    r = p.process(row)
    assert r["review_reason"] == "NO_USEFUL_TEXT" and not p.events


def test_ambiguous_reaches_human_review(row):
    row["return_reason_text"] = "not good"
    result = Pipeline().process(row)
    assert result["escalated"] and result["needs_review"]
    assert result["model_b_prediction"]["primary_reason"] == "unclear"


def test_review_updates_analytics_without_changing_evaluation(row):
    row["return_reason_text"] = "not good"
    source = pd.DataFrame([row])
    original = Pipeline().process(row)
    labels = pd.DataFrame([{"return_id": "R1", "expected_primary_reason": "fit", "expected_sub_reason": "too_small", "expected_body_area": "chest"}])
    before, _ = evaluate([original], labels)
    reviewed = review_result(original, "fit", "too_small", "chest")
    after, _ = evaluate([reviewed], labels)
    assert before == after
    assert intelligence(final_frame(source, [original]), "sku").empty
    assert intelligence(final_frame(source, [reviewed]), "sku").iloc[0].fit == 1
    assert reviewed["automated_prediction"] == original["automated_prediction"]
    assert len(reviewed["review_history"]) == 1


def test_full_demo_preserves_all_rows_and_discovers_patterns(sample):
    source, labels = split_data(sample)
    p = Pipeline()
    results = [p.process(row) for row in source[is_other(source)].to_dict("records")]
    frame = final_frame(source, results)
    assert len(results) == 440 and len(frame) == 1000
    assert frame.return_id.nunique() == 1000
    assert frame.status.eq("EXISTING_DROPDOWN").sum() == 560
    top = findings(frame).iloc[0]
    assert (top.sku, top.primary_reason, top.sub_reason, top.body_area) == ("KRT-184", "fit", "too_small", "chest")
    vendors = intelligence(frame[is_other(frame)], "vendor")
    assert vendors.sort_values("quality", ascending=False).iloc[0].vendor == "Vendor_12"
    assert any(r["needs_review"] for r in results)
    metrics, confusion = evaluate(results, labels)
    assert metrics["Evaluated Other records"] == 440 and confusion.to_numpy().sum() == 440


def test_export_escapes_formula_injection():
    content = csv_export(pd.DataFrame({"comment": ["=1+1", "normal"]})).decode("utf-8-sig")
    assert "'=1+1" in content


def test_missing_labels_are_not_scored(row):
    result = Pipeline().process(row)
    labels = pd.DataFrame([dict(return_id="R1", expected_primary_reason="", expected_sub_reason="", expected_body_area="")])
    report, matrix = evaluate([result], labels)
    assert report["primary_reason accuracy"] is None
    assert matrix.empty
