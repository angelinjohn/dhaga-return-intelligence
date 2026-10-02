"""Offline rules for UI demonstrations. Not an LLM or a quality benchmark.

Only the comment is read. No SKU/vendor exceptions, label lookups, or cached truth.
"""
import re
from .schemas import Classification, PrimaryPrediction, Attributes, unclear


def demo_classify(text: str, strong=False):
    t = text.lower()
    body = "none"
    for area, words in {"chest": ["chest", "upper body"], "waist": ["waist", "kamr"],
                        "shoulder": ["shoulder", "kandh"], "sleeves": ["sleeve", "baazu", "arms"],
                        "length": ["length", "long", "short", "lamba", "neeche"],
                        "hips": ["hip"], "neck": ["neck"], "thigh": ["thigh"]}.items():
        if any(w in t for w in words):
            body = area
            break
    rules = [
        ("wrong_item", "wrong_product_or_variant", ["wrong", "dusra product"]),
        ("delivery_issue", "package_damage", ["package damaged"]),
        ("delivery_issue", "late_delivery", ["late", "delay", "date miss"]),
        ("damaged_defective", "hole", ["hole"]),
        ("damaged_defective", "zip", ["zip"]),
        ("damaged_defective", "button", ["button"]),
        ("damaged_defective", "stitching", ["stitching open", "stitch torn"]),
        ("damaged_defective", "general_defect", ["defective", "piece damaged"]),
        ("product_not_as_expected", "shrinkage_concern", ["shrink"]),
        ("product_not_as_expected", "transparency", ["transparent", "see through"]),
        ("quality_issue", "material_mismatch", ["synthetic", "expected cotton"]),
        ("quality_issue", "comfort", ["itchy", "material comfortable"]),
        ("quality_issue", "fabric_quality", ["fabric", "material cheap", "kapda", "rough", "quality photo"]),
        ("appearance_issue", "print_mismatch", ["print", "design photo"]),
        ("appearance_issue", "shade_mismatch", ["shade", "darker", "dull"]),
        ("appearance_issue", "colour_mismatch", ["colour", "color"]),
        ("product_not_as_expected", "comfort", ["pehenne mein comfortable"]),
        ("product_not_as_expected", "occasion_unsuitable", ["office wear", "mehndi", "festive"]),
        ("product_not_as_expected", "style_mismatch", ["look", "model pe"]),
        ("changed_mind", "preference_or_no_longer_needed", ["pasand", "not needed", "nahi chahiye", "didn't like", "occasion cancel"]),
    ]
    matches = [(p, s) for p, s, words in rules if any(w in t for w in words)]
    fit_words = ["tight", "small", "chota", "choti", "snug", "kheench", "space nahi", "loose", "bada", "badi", "big", "long", "short", "lamba"]
    if body != "none" and (any(w in t for w in fit_words) or "fit nahi" in t or "move nahi" in t or "zyada" in t or "jyada" in t or "extra" in t or "length kam" in t):
        if body == "length":
            sub = "too_short" if any(w in t for w in ["short", "chota", "kam"]) else "too_long"
        elif any(w in t for w in ["loose", "bada", "badi", "big", "drop"]):
            sub = "too_large"
        else:
            sub = "too_small"
        matches.insert(0, ("fit", sub))
    if not matches:
        return unclear(text)
    primary, sub = matches[0]
    mixed = len({p for p, _ in matches}) > 1
    ambiguous = "fit nahi" in t or "move nahi" in t
    confidence = 0.65 if mixed else (0.81 if ambiguous and not strong else 0.93)
    return Classification(primary_reason=primary, sub_reason=sub,
                          body_area=body if primary == "fit" else "none",
                          confidence=confidence, needs_review=mixed,
                          evidence_text=text[:500], explanation="Offline keyword demonstration; verify with live models.")


def demo_response(schema, payload, role):
    prediction = demo_classify(payload["text"], strong=role == "B")
    if schema is PrimaryPrediction:
        return PrimaryPrediction(primary_reason=prediction.primary_reason, confidence=prediction.confidence,
                                 needs_review=prediction.needs_review,
                                 review_reason="AMBIGUOUS_TEXT" if prediction.needs_review else "NONE")
    if schema is Attributes:
        return Attributes(**prediction.model_dump(exclude={"primary_reason"}))
    return prediction
