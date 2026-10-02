import math


def token_estimate(text):
    return max(1, math.ceil(len(str(text)) / 4))


def cost_usd(input_tokens, output_tokens, config):
    if not config.input_price or not config.output_price:
        return None
    return (input_tokens * config.input_price + output_tokens * config.output_price) / 1_000_000
