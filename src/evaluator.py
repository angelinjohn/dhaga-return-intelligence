import pandas as pd

# Only the documented nomenclature alias is normalized, only after inference.
LABEL_ALIASES = {"defect": "general_defect"}


def evaluate(results, labels):
    if not results:
        return {}, pd.DataFrame()
    predictions = []
    for r in results:
        predictions.append({"return_id": r["return_id"], **r["automated_prediction"],
                            "status": r["automated_status"], "escalated": r["escalated"],
                            "schema_failures": r["schema_failures"]})
    d = pd.DataFrame(predictions).merge(labels, on="return_id", validate="one_to_one")
    metrics = {"Evaluated Other records": len(d)}
    for field in ["primary_reason", "sub_reason", "body_area"]:
        target = f"expected_{field}"
        expected = d[target].replace(LABEL_ALIASES) if field == "sub_reason" else d[target]
        mask = expected.ne("")
        if field == "body_area":
            mask &= expected.ne("none")
        metrics[f"{field} accuracy"] = float(d.loc[mask, field].eq(expected[mask]).mean()) if mask.any() else None
        metrics[f"{field} labeled records"] = int(mask.sum())
    labeled = d.expected_primary_reason.ne("")
    correct = d.primary_reason.eq(d.expected_primary_reason)
    auto_a = d.status.eq("CLASSIFIED_MODEL_A")
    auto_b = d.status.eq("CLASSIFIED_MODEL_B")
    for name, mask in [("Model A auto-accepted accuracy", auto_a), ("Model B accepted accuracy", auto_b),
                       ("Final automated accuracy", auto_a | auto_b)]:
        mask &= labeled
        metrics[name] = float(correct[mask].mean()) if mask.any() else None
        metrics[name + " denominator"] = int(mask.sum())
    metrics.update({"Model A auto-accept rate": float(auto_a.mean()),
                    "Model B escalation rate": float(d.escalated.mean()),
                    "Human review routing rate": float(d.status.isin(["NEEDS_HUMAN_REVIEW", "PROCESSING_ERROR"]).mean()),
                    "Rows with schema failure rate": float(d.schema_failures.gt(0).mean())})
    confusion = pd.crosstab(d.loc[labeled, "expected_primary_reason"], d.loc[labeled, "primary_reason"],
                           rownames=["Expected"], colnames=["Predicted"])
    return metrics, confusion
