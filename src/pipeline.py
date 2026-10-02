import json
import time
from uuid import uuid4

from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from .config import Settings
from .costing import cost_usd, token_estimate
from .demo import demo_response
from .ingestion import model_input
from .models import get_model
from .prompts import PRIMARY_PROMPT, EXTRACTION_PROMPT, STRONG_PROMPT, PROMPT_VERSION
from .routing import SchemaFailure, TechnicalFailure, route_reason
from .schemas import Attributes, Classification, PrimaryPrediction, TAXONOMY, check_evidence, unclear


def is_transient(error):
    status = getattr(error, "status_code", None)
    return isinstance(error, (TimeoutError, ConnectionError)) or status in (408, 429, 500, 502, 503, 504) or type(error).__name__ in {
        "APITimeoutError", "APIConnectionError", "RateLimitError", "InternalServerError", "ServiceUnavailable", "ResourceExhausted"
    }


class Pipeline:
    def __init__(self, settings: Settings | None = None, demo=True, model_factory=get_model):
        self.settings = settings or Settings()
        self.settings.validate()
        self.demo = demo
        self.events = []
        self.models = {}
        self.factory = model_factory
        self.run_id = str(uuid4())

    def preflight(self):
        if not self.demo:
            for cfg in [self.settings.model_a, self.settings.model_b, self.settings.fallback]:
                if cfg and cfg.identity not in self.models:
                    self.models[cfg.identity] = self.factory(cfg, self.settings.timeout)

    def _call(self, schema, prompt, payload, role, row_id, cfg, fallback=False):
        start = time.perf_counter()
        event = dict(return_id=row_id, role=role, model="offline-rules" if self.demo else cfg.identity,
                     stage=schema.__name__, technical_fallback=fallback, prompt_version=PROMPT_VERSION,
                     input_tokens=None, output_tokens=None, token_source="unavailable",
                     cost_usd=None, error=None, outcome="error")
        try:
            if self.demo:
                result = demo_response(schema, payload, role)
                event.update(input_tokens=0, output_tokens=0, token_source="offline", cost_usd=0.0)
            else:
                if cfg.identity not in self.models:
                    self.models[cfg.identity] = self.factory(cfg, self.settings.timeout)
                chain = prompt | self.models[cfg.identity].with_structured_output(schema, include_raw=True)
                response = chain.invoke(payload, config={"tags": [PROMPT_VERSION, role],
                    "metadata": {"run_id": self.run_id, "return_id": row_id, "technical_fallback": fallback}})
                raw = response.get("raw")
                usage = getattr(raw, "usage_metadata", None) or {}
                if "input_tokens" in usage and "output_tokens" in usage:
                    ins, outs = usage["input_tokens"], usage["output_tokens"]
                    token_source = "provider"
                else:
                    ins = token_estimate(prompt.invoke(payload).to_string() + json.dumps(schema.model_json_schema()))
                    outs = token_estimate(str(getattr(raw, "content", "")) + str(getattr(raw, "tool_calls", "")))
                    token_source = "estimated"
                event.update(input_tokens=ins, output_tokens=outs, token_source=token_source, cost_usd=cost_usd(ins, outs, cfg))
                if response.get("parsing_error") or response.get("parsed") is None:
                    raise SchemaFailure("Invalid structured output")
                result = schema.model_validate(response["parsed"])
            if isinstance(result, Attributes):
                check_evidence(result, payload["text"])
                if schema is Attributes and result.sub_reason not in TAXONOMY[payload["primary_reason"]]:
                    raise SchemaFailure("Incompatible sub-reason")
                if schema is Attributes and payload["primary_reason"] != "fit" and result.body_area != "none":
                    raise SchemaFailure("Unsupported body area")
            event["outcome"] = "success"
            return result
        except (ValidationError, ValueError) as error:
            event["error"] = "SCHEMA_FAILURE"
            raise SchemaFailure("Schema or evidence validation failed") from error
        except Exception as error:
            event["error"] = type(error).__name__
            if is_transient(error):
                raise TechnicalFailure(type(error).__name__) from error
            raise
        finally:
            event["latency_seconds"] = time.perf_counter() - start
            self.events.append(event)

    def invoke(self, schema, prompt, payload, role, row_id):
        cfg = self.settings.model_a if role == "A" else self.settings.model_b
        # Native structured-output retry once. Transport failures have a separate fallback.
        def runnable(config, fallback=False):
            return RunnableLambda(lambda data: self._call(schema, prompt, data, role, row_id, config, fallback)).with_retry(
                retry_if_exception_type=(SchemaFailure, TechnicalFailure), stop_after_attempt=2,
                wait_exponential_jitter=False)
        chain = runnable(cfg)
        if self.settings.fallback and not self.demo:
            chain = chain.with_fallbacks([runnable(self.settings.fallback, True)], exceptions_to_handle=(TechnicalFailure,))
        return chain.invoke(payload)

    def process(self, row):
        start = time.perf_counter()
        initial = len(self.events)
        row_id = row["return_id"]
        payload = model_input(row)  # The only gateway into prompt inputs.
        result = {**row, "model_a_prediction": None, "model_b_prediction": None,
                  "escalated": False, "escalation_reason": "", "review_reason": "",
                  "status": "NEEDS_HUMAN_REVIEW", "reviewed": False, "review_history": [],
                  "run_id": self.run_id, "mode": "offline_demo" if self.demo else "live"}
        prediction = unclear(payload["text"])
        reason = None
        if not any(c.isalnum() for c in payload["text"]):
            reason = "NO_USEFUL_TEXT"
            result["review_reason"] = reason
        else:
            try:
                primary = self.invoke(PrimaryPrediction, PRIMARY_PROMPT, payload, "A", row_id)
                result["model_a_primary"] = primary.model_dump()
                attrs = self.invoke(Attributes, EXTRACTION_PROMPT, {
                    **payload, "primary_reason": primary.primary_reason,
                    "subtaxonomy": ", ".join(TAXONOMY[primary.primary_reason])}, "A", row_id)
                prediction = Classification(**{**attrs.model_dump(), "primary_reason": primary.primary_reason,
                    "confidence": min(primary.confidence, attrs.confidence),
                    "needs_review": primary.needs_review or attrs.needs_review or primary.review_reason != "NONE" or primary.primary_reason == "unclear"})
                result["model_a_prediction"] = prediction.model_dump()
                reason = route_reason(prediction, self.settings.threshold_a)
                if primary.review_reason != "NONE":
                    reason = primary.review_reason
            except SchemaFailure:
                reason = "SCHEMA_FAILURE"
            except Exception as error:
                reason = "PROCESSING_ERROR"
                result["processing_error"] = type(error).__name__

            if reason:
                result.update(escalated=True, escalation_reason=reason)
                try:
                    previous = json.dumps(result.get("model_a_prediction") or result.get("model_a_primary") or {})
                    strong = self.invoke(Classification, STRONG_PROMPT,
                                         {**payload, "previous": previous, "reason": reason}, "B", row_id)
                    result["model_b_prediction"] = strong.model_dump()
                    disagreement = result["model_a_prediction"] and prediction.primary_reason != strong.primary_reason and prediction.primary_reason != "unclear"
                    prediction = strong
                    result["review_reason"] = ("MODEL_DISAGREEMENT" if disagreement else route_reason(strong, self.settings.threshold_b)) or ""
                    if reason == "MULTIPLE_REASONS":
                        result["review_reason"] = "MULTIPLE_REASONS"
                    result["status"] = "NEEDS_HUMAN_REVIEW" if result["review_reason"] else "CLASSIFIED_MODEL_B"
                except SchemaFailure:
                    result.update(review_reason="SCHEMA_FAILURE", status="NEEDS_HUMAN_REVIEW")
                except Exception as error:
                    result.update(review_reason="PROCESSING_ERROR", status="PROCESSING_ERROR", processing_error=type(error).__name__)
            else:
                result["status"] = "CLASSIFIED_MODEL_A"

        result.update(prediction.model_dump())
        result["needs_review"] = result["status"] in ("NEEDS_HUMAN_REVIEW", "PROCESSING_ERROR")
        result["automated_prediction"] = prediction.model_dump()
        result["automated_status"] = result["status"]
        events = self.events[initial:]
        result["schema_failures"] = sum(e["error"] == "SCHEMA_FAILURE" for e in events)
        result["processing_errors"] = sum(e["outcome"] == "error" and e["error"] != "SCHEMA_FAILURE" for e in events)
        result["technical_fallback"] = any(e["technical_fallback"] for e in events)
        successful = [e for e in events if e["outcome"] == "success"]
        result["classifier_model"] = successful[-1]["model"] if successful else "none"
        result["cost_usd"] = sum(e["cost_usd"] for e in events) if all(e["cost_usd"] is not None for e in events) else None
        result["latency_seconds"] = time.perf_counter() - start
        return result
