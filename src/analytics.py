import pandas as pd
from .ingestion import is_other

DROPDOWN_MAP = {
    "size/fit": "fit", "quality/fabric": "quality_issue", "colour mismatch": "appearance_issue",
    "damaged/defective": "damaged_defective", "wrong item": "wrong_item",
    "changed mind": "changed_mind", "delivery issue": "delivery_issue",
    "product not as expected": "product_not_as_expected",
}


def final_frame(source, results):
    records = {r["return_id"]: r for r in results}
    rows = []
    for row in source.to_dict("records"):
        if row["return_id"] in records:
            rows.append(records[row["return_id"]].copy())
        else:
            other = row["return_reason_dropdown"].strip().casefold() == "other"
            rows.append({**row, "primary_reason": "unprocessed" if other else DROPDOWN_MAP.get(row["return_reason_dropdown"].strip().casefold(), "unmapped_dropdown"),
                         "sub_reason": "", "body_area": "none", "confidence": None,
                         "needs_review": False, "status": "PENDING" if other else "EXISTING_DROPDOWN",
                         "reviewed": False, "escalated": False})
    return pd.DataFrame(rows)


def accepted(frame):
    return frame[frame.status.isin(["CLASSIFIED_MODEL_A", "CLASSIFIED_MODEL_B", "REVIEWED_HUMAN", "EXISTING_DROPDOWN"]) & ~frame.primary_reason.isin(["unclear", "unmapped_dropdown"])]


def distribution(frame, field):
    if frame.empty:
        return pd.DataFrame(columns=[field, "returns"])
    return frame.groupby(field, dropna=False).size().reset_index(name="returns").sort_values("returns", ascending=False)


def intelligence(frame, dimension):
    """Denominator is classified returned records in each group, never units sold."""
    df = accepted(frame).copy()
    if df.empty:
        return pd.DataFrame()
    for label, mask in {
        "fit": df.primary_reason.eq("fit"), "too_small": df.sub_reason.eq("too_small"),
        "too_large": df.sub_reason.eq("too_large"), "quality": df.primary_reason.eq("quality_issue"),
        "appearance": df.primary_reason.eq("appearance_issue"), "defects": df.primary_reason.eq("damaged_defective")
    }.items():
        df[label] = mask.astype(int)
    result = df.groupby(dimension).agg(classified_returns=("return_id", "size"), fit=("fit", "sum"),
        too_small=("too_small", "sum"), too_large=("too_large", "sum"), quality=("quality", "sum"),
        appearance=("appearance", "sum"), defects=("defects", "sum")).reset_index()
    result["quality_share_pct"] = result.quality / result.classified_returns * 100
    return result.sort_values("classified_returns", ascending=False)


def findings(frame):
    """Generic count-based investigation priorities. No hardcoded product/vendor findings."""
    df = accepted(frame)
    df = df[is_other(df)]
    if df.empty:
        return pd.DataFrame(columns=["sku", "primary_reason", "sub_reason", "body_area", "returns"])
    return (df.groupby(["sku", "primary_reason", "sub_reason", "body_area"]).size()
            .reset_index(name="returns").sort_values("returns", ascending=False))
