from pathlib import Path
import json
from typing import Tuple, Dict, List

import pandas as pd

from .LOS_config import (
    LOS_DATA_PATH,
    OUTPUT_PATH,
    LOS_START_ROW,
    LOS_COL_CONFIG,
)
from .LOS_loader import LOSLoader


def run_los_pipeline() -> Tuple[pd.DataFrame, List[Dict]]:
    """Process LOS data and return combined dataframe and document list."""
    print("🚀 Starting LOS processing...")

    loader = LOSLoader(LOS_DATA_PATH, config=LOS_COL_CONFIG)

    print("📂 Loading LOS sheets...")
    loader.load_all_sheets()

    print("🧹 Cleaning LOS sheets...")
    cleaned_sheets = loader.clean_all_sheets(start_row=LOS_START_ROW)

    print("🔗 Merging LOS sheets...")
    combined_df = loader.merge_data()
    print(f"✅ Combined Shape: {combined_df.shape}")

    print("📄 Converting LOS data to documents...")
    documents = loader.to_documents()
    print(f"✅ Generated {len(documents)} LOS documents")

    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    for sheet_name, df in cleaned_sheets.items():
        safe_name = sheet_name.replace(" ", "_").replace("/", "_").lower()
        df.to_csv(OUTPUT_PATH / f"{safe_name}_los_cleaned.csv", index=False)

    combined_df.to_csv(OUTPUT_PATH / "los_merged_complete.csv", index=False)

    documents_output = OUTPUT_PATH / "los_documents.json"
    with open(documents_output, "w", encoding="utf-8") as f:
        json.dump(documents, f, indent=2, ensure_ascii=False)

    print(f"💾 Outputs saved to {OUTPUT_PATH}")
    return combined_df, documents


if __name__ == "__main__":
    combined_df, documents = run_los_pipeline()
