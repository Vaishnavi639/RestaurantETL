#!/usr/bin/env python3

import argparse
from pathlib import Path
from datetime import datetime
import logging

from restaurant_etl.extractors.pdf_image_extractor import PDFImageExtractor
from restaurant_etl.parsers.image_llm_parser import ImageLLMMenuParser
from restaurant_etl.models.menu_models import MenuItem, MenuData

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# PROCESS SINGLE FILE (IMAGE MODE)
# ============================================================

def process_single_menu(file_path: str, output_dir: str = "output"):
    print("\n" + "=" * 70)
    print("  MENU EXTRACTION PIPELINE (IMAGE → LLM → CSV)")
    print("=" * 70 + "\n")

    file_path = Path(file_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    restaurant_name = file_path.stem.replace("_", " ").title()

    print(f" File: {file_path.name}")
    print(f" Restaurant: {restaurant_name}")
    print(f" Mode: IMAGE + GPT-4o Vision\n")

    # -----------------------------------------
    # STEP 1 — PDF → IMAGES
    # -----------------------------------------
    print(" STEP 1: Converting PDF to images")
    print("-" * 70)

    extractor = PDFImageExtractor()
    images = extractor.extract_images(str(file_path))

    if not images:
        print(" ❌ No images extracted")
        return None

    print(f" Extracted {len(images)} page images\n")

    # -----------------------------------------
    # STEP 2 — IMAGE → LLM
    # -----------------------------------------
    print(" STEP 2: Parsing images using GPT-4o Vision")
    print("-" * 70)

    parser = ImageLLMMenuParser()
    raw_items = parser.parse_images(images)

    if not raw_items:
        print(" ❌ No items extracted by LLM")
        return None

    print(f" Extracted {len(raw_items)} raw items\n")

    # -----------------------------------------
    # STEP 3 — NORMALIZE + ENFORCE REQUIRED FIELDS
    # -----------------------------------------
    final_items = []
    last_category = None

    for item in raw_items:
        name = item.get("item_name")
        price = item.get("price")
        category = item.get("category")

        # ❌ HARD FAIL CONDITIONS
        if not name or price is None:
            continue

        # ✅ CATEGORY FIX
        if category:
            last_category = category
        else:
            category = last_category or "Uncategorized"

        # ✅ SUBCATEGORY FIX (ALWAYS REQUIRED)
        subcategory = item.get("subcategory") or category

        try:
            final_items.append(
                MenuItem(
                    item_name=name.strip(),
                    category=category.strip(),
                    subcategory=subcategory.strip(),
                    price=float(price)
                )
            )
        except Exception as e:
            logger.warning(f"Skipping invalid item: {item} | {e}")

    menu_data = MenuData(
    restaurant_name=restaurant_name,
    items=final_items,
    total_items=len(final_items),
    extraction_metadata={
        "source": "vision_pdf",
        "raw_items_extracted": len(raw_items)
    }
)


    # -----------------------------------------
    # STEP 4 — SAVE CSV
    # -----------------------------------------
    print(" STEP 4: Saving results")
    print("-" * 70)

    df = menu_data.to_dataframe()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = output_dir / f"{file_path.stem}_vision_{timestamp}.csv"
    df.to_csv(out_path, index=False)

    print(f" ✅ Saved CSV: {out_path}")
    print(f" Rows: {len(df)} | Columns: {len(df.columns)}\n")

    print(" PREVIEW")
    print("=" * 70)
    print(df[["item_name", "category", "price"]].head(15).to_string(index=False))
    print("=" * 70)

    return df


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="PDF file or folder")
    parser.add_argument("--output", default="output")
    args = parser.parse_args()

    path = Path(args.input)

    if path.is_file():
        process_single_menu(str(path), args.output)
    else:
        for f in path.iterdir():
            if f.suffix.lower() == ".pdf":
                process_single_menu(str(f), args.output)


if __name__ == "__main__":
    main()

