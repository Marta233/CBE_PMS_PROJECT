from pathlib import Path
import sys
import json
import pandas as pd

# Add project root (better than cwd)
sys.path.insert(0, str(Path.cwd()))

from .config import DATA_PATH, OUTPUT_PATH, COL_CONFIG, START_ROW
from .bsc_loader import BSCLoader


def run_bsc_pipeline() -> tuple[pd.DataFrame, list]:
    """
    BSC pipeline (all divisions in the workbook):
    1. Load every sheet
    2. Clean each sheet (division comes from the sheet name, via the registry)
    3. Merge
    4. Convert to documents
    5. Save outputs
    """
    print("🚀 Starting BSC processing...")

    loader = BSCLoader(DATA_PATH, config=COL_CONFIG)
    loader.load_all_sheets()
    cleaned = loader.clean_all_sheets(start_row=START_ROW)
    combined_df = loader.merge_data()
    print(f"Shape: {combined_df.shape}")

    documents = loader.to_documents()
    print(f"Generated {len(documents)} documents")

    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    for sheet_name, df in cleaned.items():
        safe = "".join(ch if ch.isalnum() else "_" for ch in sheet_name).strip("_").lower()
        df.to_csv(OUTPUT_PATH / f"bsc_{safe}_cleaned.csv", index=False)
    combined_df.to_csv(OUTPUT_PATH / "bsc_merged_complete.csv", index=False)

    output_file = OUTPUT_PATH / "bsc_documents.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(documents, f, indent=2, ensure_ascii=False)

    print(f"✅ Documents saved at: {output_file}")
    return combined_df, documents


if __name__ == "__main__":
    run_bsc_pipeline()
