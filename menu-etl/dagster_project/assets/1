# dagster_project/assets/menu_assets.py (patch snippet)
from dagster import asset
from pathlib import Path
import logging

# compute project root reliably
PROJECT_ROOT = Path(__file__).resolve().parents[1].parent  # menu-etl/
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"

@asset
def menu_etl_asset() -> str:
    input_dir = INPUT_DIR
    output_dir = OUTPUT_DIR
    output_dir.mkdir(exist_ok=True)

    if not input_dir.exists():
        raise FileNotFoundError(f"Input folder not found: {input_dir}")

    extractor = UniversalExtractor()
    parser = LLMMenuParser()

    results = []
    for file in input_dir.iterdir():
        try:
            res = extractor.extract(str(file))
            if not res.get('success'):
                logging.warning(f"Extraction failed for {file}")
                continue
            menu_data = parser.parse_menu(res.get('text'), restaurant_name=file.stem)
            df = menu_data.to_dataframe()
            out_file = output_dir / f"{file.stem}_extracted.csv"
            df.to_csv(out_file, index=False)
            results.append(str(out_file))
        except Exception as e:
            logging.exception(f"Failed to process {file}: {e}")
    return ";".join(results)
