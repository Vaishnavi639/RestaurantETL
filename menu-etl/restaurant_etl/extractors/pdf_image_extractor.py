from pdf2image import convert_from_path
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class PDFImageExtractor:
    def extract_images(self, pdf_path: str):
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(pdf_path)

        logger.info(f"Converting PDF to images: {pdf_path.name}")

        images = convert_from_path(
            pdf_path,
            dpi=300,
            fmt="png"
        )

        logger.info(f"Extracted {len(images)} page images")
        return images

