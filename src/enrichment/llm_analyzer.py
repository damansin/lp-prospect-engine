import json
import logging
import time
from openai import OpenAI, RateLimitError, APIError
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log,
)
from src.config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_TEMPERATURE
from src.enrichment.prompts import (
    ENRICHMENT_SYSTEM_PROMPT,
    ENRICHMENT_USER_PROMPT,
    ORG_TYPE_GUIDANCE,
)

logger = logging.getLogger(__name__)


class LLMAnalyzer:
    def __init__(self):
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set in environment")
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self._last_call_time = 0.0
        self._min_delay = 1.5  # seconds between calls to avoid rate limits

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=5, max=60),
        retry=retry_if_exception_type((RateLimitError, APIError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def analyze_organization(self, org_name: str, org_type: str, region: str,
                             search_data: dict) -> tuple[dict, int, int]:
        """Analyze search results and return (parsed_json, input_tokens, output_tokens)."""
        elapsed = time.time() - self._last_call_time
        if elapsed < self._min_delay:
            time.sleep(self._min_delay - elapsed)

        search_text = self._format_search_results(search_data)
        guidance = ORG_TYPE_GUIDANCE.get(org_type, "Analyze this organization's LP potential based on available data.")

        user_prompt = ENRICHMENT_USER_PROMPT.format(
            org_name=org_name,
            org_type=org_type,
            region=region,
            org_type_guidance=guidance,
            search_results=search_text,
        )

        response = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=OPENAI_TEMPERATURE,
            messages=[
                {"role": "system", "content": ENRICHMENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        self._last_call_time = time.time()

        tokens_in = response.usage.prompt_tokens
        tokens_out = response.usage.completion_tokens
        raw = response.choices[0].message.content

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse LLM JSON for {org_name}: {raw[:200]}")
            parsed = self._default_response(org_name)

        parsed = self._validate_response(parsed)
        return parsed, tokens_in, tokens_out

    def _format_search_results(self, search_data: dict) -> str:
        sections = []
        for label, results in search_data.get("results", {}).items():
            query = search_data.get("queries", {}).get(label, "")
            section = f"--- Search: {label} ---\nQuery: {query}\n"
            if not results:
                section += "No results found.\n"
            else:
                for i, r in enumerate(results, 1):
                    section += f"\n[{i}] {r['title']}\n    URL: {r['url']}\n    {r['content'][:500]}\n"
            sections.append(section)
        return "\n".join(sections)

    def _validate_response(self, data: dict) -> dict:
        required_fields = {
            "is_lp": "Unclear",
            "aum_estimated": "Unknown",
            "investment_mandate": "Unknown",
            "sustainability_focus": "None found",
            "emerging_manager_signals": "None found",
            "brand_recognition": "Unknown",
            "data_quality": "Low",
            "sector_fit_score": 4,
            "sector_fit_reasoning": "Insufficient public data",
            "sector_fit_confidence": "Low",
            "halo_value_score": 4,
            "halo_reasoning": "Insufficient public data",
            "halo_confidence": "Low",
            "emerging_fit_score": 4,
            "emerging_fit_reasoning": "Insufficient public data",
            "emerging_fit_confidence": "Low",
        }
        for key, default in required_fields.items():
            if key not in data or data[key] is None:
                data[key] = default

        for score_key in ["sector_fit_score", "halo_value_score", "emerging_fit_score"]:
            try:
                val = float(data[score_key])
                data[score_key] = max(1, min(10, val))
            except (ValueError, TypeError):
                data[score_key] = 4

        return data

    def _default_response(self, org_name: str) -> dict:
        return {
            "is_lp": "Unclear",
            "lp_reasoning": f"Could not parse LLM response for {org_name}",
            "aum_estimated": "Unknown",
            "investment_mandate": "Unknown",
            "sustainability_focus": "None found",
            "emerging_manager_signals": "None found",
            "brand_recognition": "Unknown",
            "key_facts": [],
            "data_quality": "Low",
            "sector_fit_score": 4,
            "sector_fit_reasoning": "Insufficient public data to score confidently",
            "sector_fit_confidence": "Low",
            "halo_value_score": 4,
            "halo_reasoning": "Insufficient public data to score confidently",
            "halo_confidence": "Low",
            "emerging_fit_score": 4,
            "emerging_fit_reasoning": "Insufficient public data to score confidently",
            "emerging_fit_confidence": "Low",
        }
