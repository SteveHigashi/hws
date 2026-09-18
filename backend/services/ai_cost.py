MODEL_CATALOG = {
    # Anthropic
    "claude-haiku-4-5-20251001": {
        "display_name": "Claude Haiku 4.5",
        "provider": "anthropic",
        "input_cost_per_mtok": 0.80,
        "output_cost_per_mtok": 4.00,
        "quality_tier": "fast",
        "description": "Fast and cost-efficient. Best for routine signal interpretation. Typically 10–15x cheaper than Sonnet.",
    },
    "claude-sonnet-4-6": {
        "display_name": "Claude Sonnet 4.6",
        "provider": "anthropic",
        "input_cost_per_mtok": 3.00,
        "output_cost_per_mtok": 15.00,
        "quality_tier": "balanced",
        "description": "Deeper reasoning and richer context. Best when insights require strategic interpretation. ~4x more than Haiku.",
    },
    "claude-opus-4-7": {
        "display_name": "Claude Opus 4.7",
        "provider": "anthropic",
        "input_cost_per_mtok": 15.00,
        "output_cost_per_mtok": 75.00,
        "quality_tier": "premium",
        "description": "Maximum analytical depth. Best for high-stakes decisions where quality matters most. ~19x more than Haiku.",
    },
    # OpenAI
    "gpt-4o-mini": {
        "display_name": "GPT-4o mini",
        "provider": "openai",
        "input_cost_per_mtok": 0.15,
        "output_cost_per_mtok": 0.60,
        "quality_tier": "fast",
        "description": "OpenAI's fastest, cheapest model. Comparable speed to Haiku, ~5x lower cost. Good for bulk enrichment.",
    },
    "gpt-4o": {
        "display_name": "GPT-4o",
        "provider": "openai",
        "input_cost_per_mtok": 2.50,
        "output_cost_per_mtok": 10.00,
        "quality_tier": "balanced",
        "description": "OpenAI's flagship model. Strong reasoning, similar depth to Sonnet. Different analytical perspective.",
    },
    # Google
    "gemini-1.5-flash": {
        "display_name": "Gemini 1.5 Flash",
        "provider": "google",
        "input_cost_per_mtok": 0.075,
        "output_cost_per_mtok": 0.30,
        "quality_tier": "fast",
        "description": "Google's fastest model — lowest cost of all options. Ideal for high-volume or budget-constrained deployments.",
    },
    "gemini-1.5-pro": {
        "display_name": "Gemini 1.5 Pro",
        "provider": "google",
        "input_cost_per_mtok": 1.25,
        "output_cost_per_mtok": 5.00,
        "quality_tier": "balanced",
        "description": "Google's most capable model. Notably strong at pattern recognition across large datasets.",
    },
}

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = MODEL_CATALOG.get(model)
    if not pricing:
        return 0.0
    return round(
        input_tokens / 1_000_000 * pricing["input_cost_per_mtok"]
        + output_tokens / 1_000_000 * pricing["output_cost_per_mtok"],
        6,
    )
