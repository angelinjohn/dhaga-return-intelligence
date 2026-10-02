import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    name: str
    temperature: float = 0.0
    input_price: float = 0.0
    output_price: float = 0.0

    @property
    def identity(self):
        return f"{self.provider}:{self.name}"


def model_config(role, default_name):
    return ModelConfig(
        os.getenv(f"MODEL_{role}_PROVIDER", "openai"),
        os.getenv(f"MODEL_{role}_NAME", default_name),
        float(os.getenv(f"MODEL_{role}_TEMPERATURE", "0")),
        float(os.getenv(f"MODEL_{role}_INPUT_PRICE_PER_MILLION", "0")),
        float(os.getenv(f"MODEL_{role}_OUTPUT_PRICE_PER_MILLION", "0")),
    )


@dataclass
class Settings:
    model_a: ModelConfig = field(default_factory=lambda: model_config("A", "gpt-4.1-mini"))
    model_b: ModelConfig = field(default_factory=lambda: model_config("B", "gpt-4.1"))
    fallback: ModelConfig | None = field(default_factory=lambda: model_config("FALLBACK", "") if os.getenv("MODEL_FALLBACK_NAME") else None)
    threshold_a: float = field(default_factory=lambda: float(os.getenv("THRESHOLD_A", "0.85")))
    threshold_b: float = field(default_factory=lambda: float(os.getenv("THRESHOLD_B", "0.80")))
    timeout: float = 45.0

    def validate(self):
        if not (0 <= self.threshold_a <= 1 and 0 <= self.threshold_b <= 1):
            raise ValueError("Confidence thresholds must be between zero and one.")
        if self.model_a.identity == self.model_b.identity:
            raise ValueError("Model A and Model B must be different models.")
        for config in [self.model_a, self.model_b, self.fallback]:
            if config and (config.input_price < 0 or config.output_price < 0):
                raise ValueError("Token prices cannot be negative.")
