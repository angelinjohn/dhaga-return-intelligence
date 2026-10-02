from datetime import datetime, timezone
import json
import pandas as pd
from .schemas import Classification


def review_result(result, primary, sub, body, action="correct", note=""):
    # Validate edits with the same taxonomy contract. Review cannot introduce new labels.
    chosen = Classification(primary_reason=primary, sub_reason=sub, body_area=body,
        confidence=result["confidence"], needs_review=primary == "unclear",
        evidence_text=result.get("evidence_text", ""), explanation="Human review: " + action)
    updated = result.copy()
    history = list(result.get("review_history", []))
    history.append({"time": datetime.now(timezone.utc).isoformat(), "action": action, "note": note,
                    "before": {k: result[k] for k in ["primary_reason", "sub_reason", "body_area"]},
                    "after": chosen.model_dump()})
    # Confidence remains the original model signal; human approval is recorded separately.
    updated.update(chosen.model_dump(), reviewed=True, review_history=history, status="REVIEWED_HUMAN",
                   needs_review=False, review_reason="MARKED_UNCLEAR" if primary == "unclear" else "")
    return updated


def csv_export(frame):
    safe = frame.copy()
    for col in safe.columns:
        safe[col] = safe[col].map(lambda v: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
        safe[col] = safe[col].map(lambda v: "'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@")) else v)
    return safe.to_csv(index=False).encode("utf-8-sig")


def json_export(source, results, events, metadata):
    return json.dumps({"metadata": metadata, "source_records": source.to_dict("records"),
                       "results": results, "calls": events}, ensure_ascii=False, indent=2, default=str)
