from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

TAXONOMY = {
    "fit": ["too_small", "too_large", "too_long", "too_short", "unspecified_fit"],
    "quality_issue": ["fabric_quality", "material_mismatch", "comfort", "stitching_quality", "other_quality"],
    "appearance_issue": ["colour_mismatch", "shade_mismatch", "print_mismatch", "other_appearance"],
    "wrong_item": ["wrong_product_or_variant"],
    "damaged_defective": ["stitching", "zip", "hole", "button", "general_defect"],
    "changed_mind": ["preference_or_no_longer_needed"],
    "delivery_issue": ["late_delivery", "package_damage", "other_delivery"],
    "product_not_as_expected": ["style_mismatch", "transparency", "occasion_unsuitable", "comfort", "shrinkage_concern", "other_expectation_mismatch"],
    "unclear": ["insufficient_information"],
}
Primary = Literal["fit", "quality_issue", "appearance_issue", "wrong_item", "damaged_defective", "changed_mind", "delivery_issue", "product_not_as_expected", "unclear"]
Body = Literal["chest", "waist", "hips", "shoulder", "sleeves", "length", "thigh", "neck", "none"]
Sub = Literal[tuple(dict.fromkeys(s for values in TAXONOMY.values() for s in values))]
BODY_AREAS = list(Body.__args__)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PrimaryPrediction(StrictModel):
    primary_reason: Primary
    confidence: float = Field(ge=0, le=1)
    needs_review: bool
    review_reason: Literal["NONE", "LOW_CONFIDENCE", "AMBIGUOUS_TEXT", "MULTIPLE_REASONS", "NO_USEFUL_TEXT"]


class Attributes(StrictModel):
    sub_reason: Sub
    body_area: Body
    confidence: float = Field(ge=0, le=1)
    needs_review: bool
    evidence_text: str = Field(max_length=500)
    explanation: str = Field(max_length=700)


class Classification(Attributes):
    primary_reason: Primary

    @model_validator(mode="after")
    def compatible(self):
        if self.sub_reason not in TAXONOMY[self.primary_reason]:
            raise ValueError("Sub-reason is incompatible with primary reason")
        if self.primary_reason != "fit" and self.body_area != "none":
            raise ValueError("Body area is only applicable to fit")
        if self.primary_reason == "unclear" and not self.needs_review:
            raise ValueError("Unclear predictions require human review")
        return self


def check_evidence(prediction: Attributes, text: str):
    evidence = prediction.evidence_text.strip()
    if evidence and evidence.casefold() not in text.casefold():
        raise ValueError("Evidence is not a substring of the input")
    if not evidence and not prediction.needs_review:
        raise ValueError("Accepted predictions require source evidence")
    return prediction


def unclear(text: str = "") -> Classification:
    return Classification(primary_reason="unclear", sub_reason="insufficient_information",
                          body_area="none", confidence=0, needs_review=True,
                          evidence_text=text[:500], explanation="Human interpretation is required.")
