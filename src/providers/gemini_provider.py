"""Gemini model provider using Google Generative AI SDK."""

from __future__ import annotations

import os
from typing import Any, Optional

from src.providers.base import ModelProvider, ModelResponse, ModelCapabilities, Message


class GeminiProvider(ModelProvider):
    """Gemini provider using google-generativeai SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-3.8-flash",
        temperature: float = 0.2,
    ):
        self.model_name = model
        self.temperature = temperature
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        
        if not self.api_key:
            raise ValueError(
                "Gemini API key not provided. Set GEMINI_API_KEY or GOOGLE_API_KEY env var, "
                "or pass api_key to constructor."
            )
        
        # Lazy import to avoid hard dependency
        try:
            import google.generativeai as genai
        except ImportError as e:
            raise ImportError(
                "google-generativeai package not installed. Run: pip install google-generativeai"
            ) from e
        
        genai.configure(api_key=self.api_key)
        self._model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config=genai.types.GenerationConfig(
                temperature=self.temperature,
                response_mime_type="application/json",  # Force JSON output for structured responses
            ),
        )

    def _messages_to_prompt(self, messages: list[Message]) -> str:
        """Convert message list to a single prompt for Gemini."""
        parts = []
        for m in messages:
            if m.role == "system":
                parts.append(f"[System Instructions]\n{m.content}")
            elif m.role == "user":
                parts.append(f"[User]\n{m.content}")
            elif m.role == "assistant":
                parts.append(f"[Assistant]\n{m.content}")
        return "\n\n".join(parts)

    def _extract_json(self, text: str) -> dict[str, Any]:
        """Extract JSON from response text, handling markdown code fences."""
        import json
        import re
        
        # Try to find JSON in markdown code fences
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fence_match:
            return json.loads(fence_match.group(1))
        
        # Try to find bare JSON object
        brace_match = re.search(r"(\{.*\})", text, re.DOTALL)
        if brace_match:
            return json.loads(brace_match.group(1))
        
        # Fallback: try parsing entire text
        return json.loads(text)

    def complete(
        self,
        messages: list[Message],
        schema: type | None = None,
        budget_tag: str = "",
    ) -> ModelResponse:
        import google.generativeai as genai
        
        prompt = self._messages_to_prompt(messages)
        
        # Add schema instruction if provided
        if schema:
            import json
            schema_json = schema.model_json_schema()
            prompt += f"\n\n[Output Schema]\n{json.dumps(schema_json, indent=2)}"
            prompt += "\n\nRespond ONLY with valid JSON matching this schema."

        try:
            response = self._model.generate_content(prompt)
            text = response.text or ""
            
            # Parse JSON if schema expected
            parsed = None
            if schema:
                try:
                    data = self._extract_json(text)
                    parsed = schema.model_validate(data)
                except Exception:
                    # If parsing fails, return raw text
                    parsed = None
            
            # Estimate tokens (rough approximation)
            tokens_in = len(prompt) // 4
            tokens_out = len(text) // 4
            
            return ModelResponse(
                text=text,
                parsed=parsed,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost=0.0,  # Gemini free tier has no cost
                provider="gemini",
                model=self.model_name,
            )
            
        except Exception as e:
            raise RuntimeError(f"Gemini API error: {e}") from e

    async def complete_async(
        self,
        messages: list[Message],
        schema: type | None = None,
        budget_tag: str = "",
    ) -> ModelResponse:
        # Gemini SDK doesn't have native async, run sync in thread pool
        import asyncio
        return await asyncio.to_thread(self.complete, messages, schema, budget_tag)

    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            supports_vision=True,      # Gemini supports vision
            supports_audio=True,       # Gemini supports audio
            supports_structured_output=True,
            max_context_tokens=1048576,  # 1M tokens for 1.5 Pro
            cost_per_1k_input=0.0,     # Free tier
            cost_per_1k_output=0.0,
        )


class GeminiProviderOpenAICompat(ModelProvider):
    """Alternative: Gemini via OpenAI-compatible endpoint (for LiteLLM, etc.)."""
    
    def __init__(
        self,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key: str | None = None,
        model: str = "gemini-1.5-pro",
    ):
        self.base_url = base_url.rstrip("/") + "/"
        self.model = model
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        
        if not self.api_key:
            raise ValueError("Gemini API key not provided")
        
        try:
            import httpx
        except ImportError as e:
            raise ImportError("httpx package not installed. Run: pip install httpx") from e
        
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=120.0,
        )

    def complete(
        self,
        messages: list[Message],
        schema: type | None = None,
        budget_tag: str = "",
    ) -> ModelResponse:
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": 0.2,
        }
        if schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"schema": schema.model_json_schema()},
            }

        try:
            r = self._client.post("chat/completions", json=payload)
            r.raise_for_status()
            data = r.json()
            txt = data["choices"][0]["message"]["content"]
            
            parsed = None
            if schema:
                import json
                parsed = schema.model_validate_json(txt)
            
            return ModelResponse(
                text=txt,
                parsed=parsed,
                tokens_in=data["usage"]["prompt_tokens"],
                tokens_out=data["usage"]["completion_tokens"],
                cost=0.0,
                provider="gemini-openai-compat",
                model=self.model,
            )
        except Exception as e:
            raise RuntimeError(f"Gemini OpenAI-compat error: {e}") from e

    async def complete_async(
        self,
        messages: list[Message],
        schema: type | None = None,
        budget_tag: str = "",
    ) -> ModelResponse:
        import asyncio
        return await asyncio.to_thread(self.complete, messages, schema, budget_tag)

    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            supports_vision=True,
            supports_audio=True,
            supports_structured_output=True,
            max_context_tokens=1048576,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
        )