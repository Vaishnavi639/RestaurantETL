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
    def extract_text_with_pages(self, pdf_path: str):
        with open(pdf_path, "rb") as f:
            poller = self.client.begin_analyze_document(
                model_id="prebuilt-read",
                document=f
            )

        result = poller.result()

        pages = []
        for page in result.pages:
            page_lines = [line.content for line in page.lines]
            pages.append("\n".join(page_lines))

        return pages

    

