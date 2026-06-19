from __future__ import annotations

import json
import time
from typing import Any

from google import genai
from google.genai import types

from app.core.settings import get_settings


class LLMError(RuntimeError):
    pass


def _extract_json(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    start = cleaned.find("{")
    if start == -1:
        start = cleaned.find("[")
    if start == -1:
        raise LLMError("No JSON found in model response")
    return json.loads(cleaned[start:].strip())


class GeminiClient:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.gemini_api_key:
            raise LLMError("GEMINI_API_KEY is required")
        self.client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=settings.llm_timeout_seconds),
        )
        self.model = settings.gemini_model

    def _chat(self, prompt: str) -> str:
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                maxOutputTokens=2048,
                responseMimeType="application/json",
                systemInstruction="You return JSON only.",
            ),
        )
        return response.text or ""

    def classify_transactions(self, rows: list[dict]) -> list[dict]:
        prompt = {
            "task": "Classify the transactions into one category each.",
            "allowed_categories": [
                "Food",
                "Shopping",
                "Travel",
                "Transport",
                "Utilities",
                "Cash Withdrawal",
                "Entertainment",
                "Other",
            ],
            "transactions": [
                {
                    "txn_id": row.get("txn_id"),
                    "merchant": row.get("merchant"),
                    "amount": row.get("amount"),
                    "currency": row.get("currency"),
                    "status": row.get("status"),
                    "account_id": row.get("account_id"),
                    "notes": row.get("notes"),
                }
                for row in rows
            ],
            "output_shape": [{"txn_id": "string", "category": "string"}],
        }
        content = self._chat(json.dumps(prompt))
        parsed = _extract_json(content)
        return parsed if isinstance(parsed, list) else parsed.get("items", [])

    def narrative_summary(self, payload: dict) -> dict:
        prompt = {
            "task": "Summarize the financial dataset as structured JSON.",
            "required_keys": [
                "total_spend_by_currency",
                "top_3_merchants",
                "anomaly_count",
                "narrative",
                "risk_level",
            ],
            "payload": payload,
        }
        content = self._chat(json.dumps(prompt))
        parsed = _extract_json(content)
        if not isinstance(parsed, dict):
            raise LLMError("Summary response must be a JSON object")
        return parsed


def call_with_retry(callable_fn, retries: int = 3) -> Any:
    delay = 1.0
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            return callable_fn()
        except Exception as error:
            last_error = error
            if attempt == retries - 1:
                break
            time.sleep(delay)
            delay *= 2
    raise last_error or LLMError("Unknown LLM failure")
