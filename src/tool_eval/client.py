"""LMStudio client wrapper with instructor integration."""

import os
import time
from dataclasses import dataclass
from typing import TypeVar, Any

import instructor
from openai import OpenAI
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

DEFAULT_BASE_URL = "http://macstudio.local:1234/v1"


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars per token for English)."""
    if not text:
        return 0
    return len(text) // 4


@dataclass
class ModelResponse:
    """Response from model with metadata."""

    result: Any
    input_tokens: int
    output_tokens: int
    thinking_tokens: int  # Tokens spent on reasoning content
    latency_ms: int
    raw_response: dict | None = None
    thinking: str | None = None  # For thinking models
    retries: int = 0


class LMStudioClient:
    """Client for LMStudio with instructor for structured outputs."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        max_retries: int = 3,
    ):
        self.base_url = base_url or os.getenv("LMSTUDIO_BASE_URL", DEFAULT_BASE_URL)
        self.model = model
        self.max_retries = max_retries

        # Raw OpenAI client
        self._openai = OpenAI(base_url=self.base_url, api_key="not-needed")

        # Instructor-wrapped client for structured outputs
        self._instructor = instructor.from_openai(self._openai)

    def list_models(self) -> list[str]:
        """List available models from LMStudio."""
        response = self._openai.models.list()
        return [m.id for m in response.data]

    def get_current_model(self) -> str | None:
        """Get currently loaded model, or first available."""
        if self.model:
            return self.model
        models = self.list_models()
        return models[0] if models else None

    def call_with_tools(
        self,
        prompt: str,
        tools: list[dict],
        system_prompt: str | None = None,
        response_model: type[T] | None = None,
        reasoning_effort: str | None = None,
    ) -> ModelResponse:
        """Call model with tools and capture metrics.

        Args:
            prompt: User prompt
            tools: List of tools in OpenAI format
            system_prompt: Optional system prompt
            response_model: Optional Pydantic model for structured output
            reasoning_effort: For thinking models: "low", "medium", "high", or None to disable

        Returns:
            ModelResponse with result and metrics
        """
        model = self.get_current_model()
        if not model:
            raise RuntimeError("No model available")

        start_time = time.perf_counter()

        if response_model:
            # Use instructor for structured output (still uses chat/completions)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            result, completion = self._instructor.chat.completions.create_with_completion(
                model=model,
                messages=messages,
                tools=tools,
                response_model=response_model,
                max_retries=self.max_retries,
            )

            latency_ms = int((time.perf_counter() - start_time) * 1000)

            return ModelResponse(
                result=result,
                input_tokens=completion.usage.prompt_tokens if completion.usage else 0,
                output_tokens=completion.usage.completion_tokens if completion.usage else 0,
                thinking_tokens=0,
                latency_ms=latency_ms,
                raw_response=completion.model_dump() if completion else None,
                retries=0,
            )
        else:
            # Use /v1/responses API for better reasoning model support
            return self._call_responses_api(
                prompt=prompt,
                tools=tools,
                system_prompt=system_prompt,
                reasoning_effort=reasoning_effort,
                start_time=start_time,
            )

    def _call_responses_api(
        self,
        prompt: str,
        tools: list[dict],
        system_prompt: str | None,
        reasoning_effort: str | None,
        start_time: float,
    ) -> ModelResponse:
        """Call the /v1/responses API."""
        import httpx

        model = self.get_current_model()

        # Convert tools from chat/completions format to responses API format
        # From: {"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}}
        # To:   {"type": "function", "name": "...", "description": "...", "parameters": {...}}
        converted_tools = []
        for tool in tools:
            if tool.get("type") == "function" and "function" in tool:
                func = tool["function"]
                converted_tools.append({
                    "type": "function",
                    "name": func.get("name"),
                    "description": func.get("description", ""),
                    "parameters": func.get("parameters", {}),
                })
            else:
                converted_tools.append(tool)

        # Build request payload
        payload: dict[str, Any] = {
            "model": model,
            "input": prompt,
            "tools": converted_tools,
        }

        if system_prompt:
            payload["instructions"] = system_prompt

        if reasoning_effort:
            payload["reasoning"] = {"effort": reasoning_effort}

        # Make request to responses API
        response = httpx.post(
            f"{self.base_url.rstrip('/v1')}/v1/responses",
            json=payload,
            timeout=120.0,
        )
        response.raise_for_status()
        data = response.json()

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # Extract tool calls from output
        tool_calls = []
        thinking_parts = []
        output_text = None

        for item in data.get("output", []):
            if item.get("type") == "function_call":
                tool_calls.append(item)
            elif item.get("type") == "reasoning":
                # Reasoning content is nested: content[].text
                for content in item.get("content", []):
                    if content.get("type") == "reasoning_text":
                        thinking_parts.append(content.get("text", ""))
            elif item.get("type") == "message":
                # Extract text content
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        output_text = content.get("text", "")

        thinking = "\n".join(thinking_parts) if thinking_parts else None

        # Get token usage
        usage = data.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        reasoning_tokens = usage.get("output_tokens_details", {}).get("reasoning_tokens", 0)

        # If no separate reasoning tokens reported, estimate from thinking content
        if reasoning_tokens == 0 and thinking:
            reasoning_tokens = estimate_tokens(thinking)

        return ModelResponse(
            result=tool_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            thinking_tokens=reasoning_tokens,
            latency_ms=latency_ms,
            raw_response=data,
            thinking=thinking,
            retries=0,
        )

    def simple_completion(self, prompt: str, system_prompt: str | None = None) -> str:
        """Simple completion without tools - useful for LLM-as-judge scoring."""
        model = self.get_current_model()
        if not model:
            raise RuntimeError("No model available")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        completion = self._openai.chat.completions.create(
            model=model,
            messages=messages,
        )

        if completion.choices:
            return completion.choices[0].message.content or ""
        return ""
