import os
import json
import logging
import base64
from typing import List
from io import BytesIO

from dotenv import load_dotenv
from openai import AzureOpenAI

# --------------------------------------------------
# ENV + LOGGING
# --------------------------------------------------

load_dotenv()  # 🔴 REQUIRED — fixes your credential error

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --------------------------------------------------
# SYSTEM PROMPT (VISION)
# --------------------------------------------------

SYSTEM_PROMPT = """
You are reading images of a restaurant menu.

TASK:
- Extract ALL menu items visible in the images.
- For EACH item, extract:
  - item_name
  - category (if visible, else null)
  - price (number only, no currency symbol)

IMPORTANT RULES:
- Do NOT guess prices.
- Do NOT merge items.
- If an item has multiple prices (sizes/variants),
  create SEPARATE items with variant text appended to item_name.
- Maintain visual order.
- Output ONLY valid JSON.
- NO markdown. NO explanation.

OUTPUT FORMAT:
{
  "items": [
    {
      "item_name": "Item Name - Variant",
      "category": "Category or null",
      "price": 99
    }
  ]
}
"""

# --------------------------------------------------
# PARSER
# --------------------------------------------------

class ImageLLMMenuParser:
    def __init__(self):
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

        if not all([api_key, endpoint, deployment]):
            raise ValueError("Azure OpenAI credentials missing. Check .env file.")

        self.deployment = deployment
        self.client = AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version
        )

        logger.info("✓ Azure OpenAI Vision client initialized")

    # --------------------------------------------------

    def parse_images(self, images: List, batch_size: int = 2):
        all_items = []

        for i in range(0, len(images), batch_size):
            batch = images[i:i + batch_size]
            logger.info(f"Vision batch {i // batch_size + 1} with {len(batch)} images")

            content = [{"type": "text", "text": SYSTEM_PROMPT}]

            for img in batch:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": self._image_to_base64(img)
                    }
                })

            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[{"role": "user", "content": content}],
                temperature=0,
                max_tokens=2500
            )

            raw = response.choices[0].message.content
            logger.debug(f"RAW VISION OUTPUT:\n{raw[:1000]}")

            parsed = self._safe_json_load(raw)
            all_items.extend(parsed.get("items", []))

        return all_items

    # --------------------------------------------------
    # HELPERS
    # --------------------------------------------------

    def _image_to_base64(self, image):
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()

    def _safe_json_load(self, text: str):
        """
        Robust JSON extractor for vision output
        """
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start == -1 or end == -1:
                raise ValueError("No JSON object found")
            return json.loads(text[start:end])
        except Exception as e:
            logger.error("❌ Could not parse JSON from vision output")
            logger.error(text[:1000])
            return {"items": []}

