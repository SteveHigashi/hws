"""Provider-agnostic AI call layer. Routes to Anthropic, OpenAI, or Google based on model."""

from typing import AsyncGenerator, Tuple

# Maps model ID → provider
_PROVIDER_MAP = {
    "claude-haiku-4-5-20251001": "anthropic",
    "claude-sonnet-4-6":         "anthropic",
    "claude-opus-4-7":           "anthropic",
    "gpt-4o":                    "openai",
    "gpt-4o-mini":               "openai",
    "gemini-1.5-pro":            "google",
    "gemini-1.5-flash":          "google",
}


def get_provider(model: str) -> str:
    return _PROVIDER_MAP.get(model, "anthropic")


async def call_model(
    model: str,
    system: str,
    user_message: str,
    api_keys: dict,
    max_tokens: int = 1500,
) -> Tuple[str, int, int]:
    """Non-streaming call. Returns (text, input_tokens, output_tokens)."""
    provider = get_provider(model)

    if provider == "anthropic":
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=api_keys["anthropic"])
        resp = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )
        return resp.content[0].text, resp.usage.input_tokens, resp.usage.output_tokens

    if provider == "openai":
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_keys["openai"])
        resp = await client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
        )
        usage = resp.usage
        return (
            resp.choices[0].message.content,
            usage.prompt_tokens,
            usage.completion_tokens,
        )

    if provider == "google":
        import google.generativeai as genai
        genai.configure(api_key=api_keys["google"])
        gemini = genai.GenerativeModel(
            model_name=model,
            system_instruction=system,
        )
        resp = await gemini.generate_content_async(user_message)
        # Google doesn't always return token counts — estimate from text length
        text = resp.text
        in_tok = len(user_message) // 4
        out_tok = len(text) // 4
        try:
            in_tok = resp.usage_metadata.prompt_token_count
            out_tok = resp.usage_metadata.candidates_token_count
        except Exception:
            pass
        return text, in_tok, out_tok

    raise ValueError(f"Unknown provider for model: {model}")


async def stream_model(
    model: str,
    system: str,
    user_message: str,
    api_keys: dict,
    max_tokens: int = 1024,
) -> AsyncGenerator[str, None]:
    """Streaming call. Yields text chunks."""
    provider = get_provider(model)

    if provider == "anthropic":
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=api_keys["anthropic"])
        async with client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=[
                {"type": "text", "text": system},
            ],
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            async for chunk in stream.text_stream:
                yield chunk
        return

    if provider == "openai":
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_keys["openai"])
        stream = await client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            stream=True,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
        return

    if provider == "google":
        import google.generativeai as genai
        genai.configure(api_key=api_keys["google"])
        gemini = genai.GenerativeModel(model_name=model, system_instruction=system)
        async for chunk in await gemini.generate_content_async(user_message, stream=True):
            yield chunk.text
        return

    raise ValueError(f"Unknown provider for model: {model}")
