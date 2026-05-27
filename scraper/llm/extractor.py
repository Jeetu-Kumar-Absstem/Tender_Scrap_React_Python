"""
scraper/llm/extractor.py
────────────────────────
Pluggable LLM extraction layer.

Set LLM_PROVIDER=huggingface  → uses HuggingFace Inference API
Set LLM_PROVIDER=claude       → uses Anthropic Claude API

The extraction prompt and output schema are identical for both.
Swapping providers = changing one line in .env, zero code changes.
"""

from __future__ import annotations
import json
import os
import re
import structlog
from abc import ABC, abstractmethod
from tenacity import retry, stop_after_attempt, wait_exponential

log = structlog.get_logger()

# ─── Extraction prompt (provider-agnostic) ───────────────────
SYSTEM_PROMPT = """You extract government tender information and return ONLY valid JSON.
Never add explanation, markdown fences, or any text outside the JSON object.
All field values must be strings or null. document_urls must be a list."""

EXTRACTION_PROMPT = """Extract tender details from this government website text.

Return EXACTLY this JSON structure — no extra fields, no markdown:
{{
  "title": "full tender title or null",
  "reference_number": "NIT/tender/bid reference number or null",
  "organization": "issuing department or ministry or null",
  "deadline": "submission deadline in YYYY-MM-DD format or null",
  "estimated_value": "estimated value in INR as plain string or null",
  "location": "city or state or null",
  "document_urls": ["actual .pdf or .doc download URLs only, or empty list"]
}}

Rules:
- deadline MUST be YYYY-MM-DD format — convert from any format found
- Use null for missing fields — never guess
- document_urls: only real file URLs, not page links
- If multiple tenders appear, extract the most prominent one

Text:
{context_text}"""


def _parse_llm_json(raw: str) -> dict:
    """Strip markdown fences and parse JSON — handles common LLM output quirks."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


# ─── Abstract base ────────────────────────────────────────────
class BaseLLMExtractor(ABC):
    @abstractmethod
    def extract(self, context_text: str) -> dict:
        """Send context to LLM, return structured dict."""
        ...


# ─── HuggingFace provider ────────────────────────────────────
class HuggingFaceExtractor(BaseLLMExtractor):
    def __init__(self):
        import requests as req
        self._requests = req
        self.api_key = os.environ["HUGGINGFACE_API_KEY"]
        self.model   = os.getenv(
            "HUGGINGFACE_MODEL",
            "mistralai/Mistral-7B-Instruct-v0.3"
        )
        self.api_url = (
            f"https://api-inference.huggingface.co/models/{self.model}"
        )
        log.info("llm.provider", provider="huggingface", model=self.model)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    def extract(self, context_text: str) -> dict:
        prompt = (
            f"[INST] {SYSTEM_PROMPT}\n\n"
            + EXTRACTION_PROMPT.format(context_text=context_text)
            + " [/INST]"
        )
        resp = self._requests.post(
            self.api_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": 400,
                    "temperature": 0.1,
                    "return_full_text": False,
                },
            },
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json()

        # HF returns list of generated_text dicts
        if isinstance(raw, list) and raw:
            text = raw[0].get("generated_text", "")
        else:
            text = str(raw)

        return _parse_llm_json(text)


# ─── Claude (Anthropic) provider ─────────────────────────────
class ClaudeExtractor(BaseLLMExtractor):
    def __init__(self):
        import anthropic
        self.client = anthropic.Anthropic(
            api_key=os.environ["ANTHROPIC_API_KEY"]
        )
        self.model = os.getenv(
            "ANTHROPIC_MODEL",
            "claude-haiku-4-5-20251001"  # cheapest, fast enough for extraction
        )
        log.info("llm.provider", provider="claude", model=self.model)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    def extract(self, context_text: str) -> dict:
        message = self.client.messages.create(
            model=self.model,
            max_tokens=400,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": EXTRACTION_PROMPT.format(context_text=context_text),
            }],
        )
        raw = message.content[0].text
        return _parse_llm_json(raw)


# ─── Factory — reads LLM_PROVIDER from env ───────────────────
def get_llm_extractor() -> BaseLLMExtractor:
    """
    Returns the correct extractor based on LLM_PROVIDER env var.
    Call once at startup, reuse the instance for all pages.
    
    To switch: change LLM_PROVIDER in .env — zero code changes.
    """
    provider = os.getenv("LLM_PROVIDER", "huggingface").lower()

    if provider == "claude":
        return ClaudeExtractor()
    elif provider == "huggingface":
        return HuggingFaceExtractor()
    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER='{provider}'. "
            "Valid values: huggingface | claude"
        )
