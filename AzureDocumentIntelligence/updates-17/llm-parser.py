import os
import json
import time
import logging
import re
from typing import Optional, List, Dict

from dotenv import load_dotenv
load_dotenv()

from restaurant_etl.models.menu_models import MenuItem, MenuData
from restaurant_etl.parsers.prompt_templates import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

# Postprocessing import
try:
    from restaurant_etl.parsers.postprocess import expand_and_normalize_items as postprocess_fn
except Exception:
    try:
        from restaurant_etl.parsers.postprocess import postprocess_llm_items as postprocess_fn
    except Exception:
        def postprocess_fn(items):
            return items

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ============================================================
# JSON REPAIR & SALVAGE
# ============================================================

def _safe_json_load_with_repair(raw: str) -> Dict:
    if not raw:
        raise ValueError("Empty model output")

    raw = raw.strip()

    # --- Strip markdown code fences ---
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.replace("json", "", 1).strip()

    # --- Try direct parse ---
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return {"items": parsed}
        return parsed
    except Exception:
        pass

    # --- Trim trailing garbage ---
    last_obj = raw.rfind("}")
    last_arr = raw.rfind("]")
    last_pos = max(last_obj, last_arr)

    if last_pos != -1:
        candidate = raw[: last_pos + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, list):
                return {"items": parsed}
            return parsed
        except Exception:
            pass

    # --- Replace Python literals & bad chars ---
    repaired = raw
    repaired = repaired.replace("\r", " ").replace("\t", " ")
    repaired = repaired.replace("\n", "\\n")
    repaired = re.sub(r":\s*None\b", ": null", repaired)
    repaired = re.sub(r":\s*True\b", ": true", repaired)
    repaired = re.sub(r":\s*False\b", ": false", repaired)

    try:
        parsed = json.loads(repaired)
        if isinstance(parsed, list):
            return {"items": parsed}
        return parsed
    except Exception:
        pass

    # --- FINAL FALLBACK: salvage individual objects ---
    objects = re.findall(r'\{[^{}]*\}', raw, re.DOTALL)
    salvaged = []

    for obj in objects:
        try:
            salvaged.append(json.loads(obj))
        except Exception:
            continue

    if salvaged:
        logger.warning(f"⚠ Salvaged {len(salvaged)} items from partial JSON")
        return {"items": salvaged}

    raise ValueError(f"[JSON Parse Error] Could not parse model output.\nSnippet:\n{raw[:500]}")


# ============================================================
# MAIN PARSER
# ============================================================

class LLMMenuParser:
    def __init__(self):
        try:
            from openai import AzureOpenAI
        except Exception as e:
            raise ImportError("AzureOpenAI SDK missing") from e

        self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

        if not all([self.api_key, self.endpoint, self.deployment]):
            raise ValueError("Missing Azure OpenAI credentials in .env")

        self.client = AzureOpenAI(
            api_key=self.api_key,
            azure_endpoint=self.endpoint,
            api_version=self.api_version,
        )

        self.max_retries = 3
        self.max_tokens = 4096

        logger.info(f"✓ AzureOpenAI client initialized (version={self.api_version})")

    # --------------------------------------------------------

    def parse_menu(self, menu_text: str, restaurant_name: Optional[str] = None) -> MenuData:
        chunks = self._split_into_chunks(menu_text, max_chars=1000)

        all_items = []

        for i, chunk in enumerate(chunks, 1):
            logger.info(f"Calling LLM on chunk {i}/{len(chunks)} ({len(chunk)} chars)")
            parsed = self._call_llm_with_retries(chunk)
            if not parsed:
                continue

            raw_items = parsed.get("items", [])
            processed_items = postprocess_fn(raw_items)
            all_items.extend(processed_items)

        final_items = []
        for item in all_items:
            try:
                obj = MenuItem(**item)
                if obj.has_any_price():
                    final_items.append(obj)
            except Exception as e:
                logger.debug(f"Validation failed: {e}")

        return MenuData(
            restaurant_name=restaurant_name or "Unknown",
            items=final_items,
            total_items=len(final_items),
            extraction_metadata={
                "total_items_extracted": len(final_items)
            }
        )

    # --------------------------------------------------------

    def _split_into_chunks(self, text: str, max_chars: int) -> List[str]:
        parts = text.split("\n\n")
        chunks, curr = [], ""

        for p in parts:
            if len(curr) + len(p) > max_chars:
                chunks.append(curr)
                curr = p
            else:
                curr += "\n\n" + p

        if curr.strip():
            chunks.append(curr)

        return [c for c in chunks if c.strip()]

    # --------------------------------------------------------

    def _call_llm_with_retries(self, chunk: str) -> Optional[Dict]:
        delay = 1
        for attempt in range(1, self.max_retries + 1):
            try:
                return self._call_llm(chunk)
            except Exception as e:
                logger.error(f"Attempt {attempt} failed: {e}")
                if attempt == self.max_retries:
                    logger.error("❌ All retries failed.")
                    return None
                time.sleep(delay)
                delay *= 2

    # --------------------------------------------------------

    def _call_llm(self, chunk: str) -> Dict:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT_TEMPLATE.replace("{menu_text}",chunk)}
        ]

        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=messages,
            temperature=0,
            max_tokens=self.max_tokens,
            timeout=60
        )

        raw_output = response.choices[0].message.content
        return _safe_json_load_with_repair(raw_output)
