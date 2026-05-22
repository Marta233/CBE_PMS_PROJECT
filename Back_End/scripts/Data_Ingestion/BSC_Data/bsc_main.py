from pathlib import Path
import sys
import json
import pandas as pd

# Add project root (better than cwd)
sys.path.insert(0, str(Path.cwd()))

from .config import DATA_PATH,OUTPUT_PATH,RBB_SHEET,DIGITAL_SHEET,COL_CONFIG,START_ROW

from .bsc_loader import BSCLoader



def run_bsc_pipeline() -> tuple[pd.DataFrame, list]:
    """
    BSC pipeline:
    1. Load sheets
    2. Clean separately
    3. Merge
    4. Convert to documents
    5. Save outputs
    """

    print("🚀 Starting BSC processing...")

    loader = BSCLoader(DATA_PATH, config=COL_CONFIG)

    # -------------------------
    # LOAD
    # -------------------------
    print("📂 Loading sheets...")
    loader.load_separately(RBB_SHEET, DIGITAL_SHEET)

    # -------------------------
    # CLEAN RBB
    # -------------------------
    print("🧹 Cleaning RBB...")
    rbb_df = loader.clean_rbb(start_row=START_ROW)
    print(rbb_df.head())

    # -------------------------
    # CLEAN DIGITAL
    # -------------------------
    print("🧹 Cleaning Digital...")
    digital_df = loader.clean_digital(start_row=START_ROW)
    print(digital_df.head())

    # -------------------------
    # MERGE
    # -------------------------
    print("🔗 Merging...")
    combined_df = loader.merge_data()
    print(f"Shape: {combined_df.shape}")

    # -------------------------
    # DOCUMENTS
    # -------------------------
    print("📄 Converting to documents...")
    documents = loader.to_documents()
    print(f"Generated {len(documents)} documents")

    # -------------------------
    # SAVE OUTPUTS
    # -------------------------
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    rbb_df.to_csv(OUTPUT_PATH / "rbb_cleaned.csv", index=False)
    digital_df.to_csv(OUTPUT_PATH / "digital_cleaned.csv", index=False)
    combined_df.to_csv(OUTPUT_PATH / "bsc_merged_complete.csv", index=False)

    output_file = OUTPUT_PATH / "bsc_documents.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(documents, f, indent=2, ensure_ascii=False)

    print(f"✅ Documents saved at: {output_file}")

    return combined_df, documents


# -------------------------
# MAIN ENTRY POINT
# -------------------------
if __name__ == "__main__":
    run_bsc_pipeline()