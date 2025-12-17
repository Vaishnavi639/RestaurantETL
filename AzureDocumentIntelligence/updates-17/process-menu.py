#!/usr/bin/env python3
"""
MENU EXTRACTION PIPELINE (AZURE OCR → LLM → CSV)

Flow:
1. PDF → Azure Document Intelligence OCR
2. OCR Text → LLM (prompt_templates_2.py via llm_parser.py)
3. JSON → Pydantic Validation
4. DataFrame → CSV
"""

import argparse
from pathlib import Path
from datetime import datetime
import logging

from restaurant_etl.extractors.azure_ocr_extractor import AzureOCRExtractor
from restaurant_etl.parsers.llm_parser import LLMMenuParser
from restaurant_etl.models.menu_models import MenuData

# --------------------------------------------------
# LOGGING
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(name)s:%(message)s"
)
logger = logging.getLogger(__name__)

# --------------------------------------------------
# PROCESS SINGLE PDF
# --------------------------------------------------

def process_single_menu(file_path: str, output_dir: str = "output"):
    print("\n" + "=" * 70)
    print("  MENU EXTRACTION PIPELINE (AZURE OCR → LLM → CSV)")
    print("=" * 70 + "\n")

    file_path = Path(file_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    restaurant_name = file_path.stem.replace("_", " ").title()

    print(f" File: {file_path.name}")
    print(f" Restaurant: {restaurant_name}")
    print(f" Mode: AZURE OCR + GPT\n")

    # -----------------------------------------
    # STEP 1 — AZURE DOCUMENT INTELLIGENCE OCR
    # -----------------------------------------
    print(" STEP 1: Extracting text using Azure Document Intelligence")
    print("-" * 70)

    ocr = AzureOCRExtractor()
    text = ocr.extract_text(str(file_path), save_debug=True)

    if not text.strip():
        print(" ❌ No text extracted by Azure OCR")
        return None

    print(f" ✓ Extracted {len(text)} characters via Azure OCR\n")

    # -----------------------------------------
    # STEP 2 — LLM PARSING (TEXT → JSON)
    # -----------------------------------------
    print(" STEP 2: Parsing OCR text using GPT")
    print("-" * 70)

    parser = LLMMenuParser()
    menu_data: MenuData = parser.parse_menu(
        menu_text=text,
        restaurant_name=restaurant_name
    )

    if not menu_data.items:
        print(" ❌ No items extracted by LLM")
        return None

    print(f" ✓ Parsed {menu_data.total_items} items\n")

    # -----------------------------------------
    # STEP 3 — SAVE CSV
    # -----------------------------------------
    print(" STEP 3: Saving results")
    print("-" * 70)

    df = menu_data.to_dataframe()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = output_dir / f"{file_path.stem}_azureocr_{timestamp}.csv"
    df.to_csv(out_path, index=False)

    print(f" ✅ Saved CSV: {out_path}")
    print(f" Rows: {len(df)} | Columns: {len(df.columns)}\n")

    # -----------------------------------------
    # PREVIEW
    # -----------------------------------------
    print(" PREVIEW (First 15 items)")
    print("=" * 70)

    preview_cols = ["item_name", "category", "subcategory", "price"]
    cols = [c for c in preview_cols if c in df.columns]
    print(df[cols].head(15).to_string(index=False))

    print("\n" + "=" * 70)
    print(" PIPELINE COMPLETE")
    print("=" * 70)

    return df


# --------------------------------------------------
# PROCESS FOLDER
# --------------------------------------------------

def process_folder(input_folder: str, output_folder: str):
    input_folder = Path(input_folder)

    if not input_folder.exists():
        print(f" ❌ Folder not found: {input_folder}")
        return

    pdfs = [f for f in input_folder.iterdir() if f.suffix.lower() == ".pdf"]

    if not pdfs:
        print(" ❌ No PDFs found")
        return

    print(f"\n Found {len(pdfs)} PDF(s) to process\n")

    for idx, pdf in enumerate(pdfs, 1):
        print("\n" + "=" * 70)
        print(f" Processing {idx}/{len(pdfs)}: {pdf.name}")
        print("=" * 70)
        try:
            process_single_menu(str(pdf), output_folder)
        except Exception as e:
            logger.exception(f"Failed processing {pdf.name}: {e}")


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Menu ETL using Azure OCR + GPT"
    )

    parser.add_argument(
        "input",
        nargs="?",
        default="input",
        help="PDF file or folder"
    )
    parser.add_argument(
        "--output",
        default="output",
        help="Output folder"
    )

    args = parser.parse_args()
    input_path = Path(args.input)

    if input_path.is_file():
        process_single_menu(str(input_path), args.output)
    elif input_path.is_dir():
        process_folder(str(input_path), args.output)
    else:
        print(f" ❌ Path not found: {input_path}")


if __name__ == "__main__":
    main()
