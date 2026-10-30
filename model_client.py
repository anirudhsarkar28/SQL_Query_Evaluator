"""OpenAI-compatible client for the local LM Studio server."""
import os
import time
from typing import Any

import requests

BASE_URL = os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")
MODEL_NAME = os.getenv("LM_STUDIO_MODEL", "gemma-3-4b")
API_KEY = os.getenv("LM_STUDIO_API_KEY", "lm-studio")  # Local server commonly accepts any non-empty key.

SYSTEM_PROMPT = """You are a careful SQL debugging assistant.
Return ONLY a JSON object with these keys:
{
  "error_type": "short category",
  "explanation": "what is wrong and why",
  "fixed_sql": "one corrected SQL statement, or empty string if uncertain",
  "assumptions": "any assumptions made"
}
Use only tables and columns in the supplied schema. Preserve the user's apparent intent.
Do not propose DROP, ALTER, TRUNCATE, INSERT, UPDATE, or DELETE statements as a repair.
Do not wrap the JSON in Markdown fences. If the request is ambiguous, say so in assumptions.
"""

class ModelResponseError(ValueError):
    """Raised when the model server returns an unusable completion."""


def generate_fix(
    broken_sql: str,
    schema: str,
    dialect: str = "SQLite",
    timeout: int = 120,
) -> dict[str, Any]:
    """Call the local OpenAI-compatible LM Studio endpoint and return response + latency."""
    if not broken_sql.strip():
        raise ValueError("Enter a SQL query before requesting a repair.")
    if not schema.strip():
        raise ValueError("Provide the database schema before requesting a repair.")
    if timeout <= 0:
        raise ValueError("timeout must be greater than zero.")

    url = BASE_URL.rstrip("/") + "/chat/completions"
    prompt = f"""SQL dialect: {dialect}
Database schema:
{schema}

Broken SQL:
{broken_sql}

Explain the error and propose a safe corrected SELECT query."""
    started = time.perf_counter()
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "max_tokens": 700,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    elapsed = time.perf_counter() - started
    try:
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise ModelResponseError(
            "The model server returned an invalid chat completion response."
        ) from exc
    if not isinstance(content, str) or not content.strip():
        raise ModelResponseError("The model server returned an empty completion.")
    return {"raw_response": content, "latency_seconds": round(elapsed, 4),
            "model": payload.get("model", MODEL_NAME)}
