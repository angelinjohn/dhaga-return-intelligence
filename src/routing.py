from .schemas import Classification


def route_reason(result: Classification, threshold: float) -> str | None:
    if result.primary_reason == "unclear":
        return "AMBIGUOUS_TEXT"
    if result.needs_review:
        return "AMBIGUOUS_TEXT"
    if result.confidence < threshold:
        return "LOW_CONFIDENCE"
    return None


class SchemaFailure(ValueError):
    """Schema or semantic validation failed at a model boundary."""


class TechnicalFailure(RuntimeError):
    """Transient transport, timeout, rate limit, or provider outage."""
