import os
from pathlib import Path
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)


class AzureOCRExtractor:
    def __init__(self):
        endpoint = os.getenv("AZURE_DOC_INTEL_ENDPOINT")
        key = os.getenv("AZURE_DOC_INTEL_KEY")

        if not endpoint or not key:
            raise ValueError("Azure Document Intelligence credentials missing")

        self.client = DocumentAnalysisClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(key)
        )

    def extract_text(self, pdf_path: str, save_debug: bool = True) -> str:
        """
        Extract readable text from scanned or image-based PDFs using Azure OCR.
        """
        pdf_path = Path(pdf_path)

        with open(pdf_path, "rb") as f:
            poller = self.client.begin_analyze_document(
                model_id="prebuilt-read",
                document=f
            )

        result = poller.result()

        lines = []
        for page in result.pages:
            for line in page.lines:
                lines.append(line.content)

        text = "\n".join(lines)

        # 🔹 SAVE OCR TEXT FOR VISIBILITY (IMPORTANT)
        if save_debug:
            debug_dir = Path("debug_azure_ocr")
            debug_dir.mkdir(exist_ok=True)
            out_file = debug_dir / f"{pdf_path.stem}_ocr.txt"
            out_file.write_text(text, encoding="utf-8")
            logger.info(f"✓ Azure OCR text saved to {out_file}")

        return text
