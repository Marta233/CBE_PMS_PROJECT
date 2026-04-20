from pathlib import Path
import sys
import json

# Add current directory to path
sys.path.insert(0, str(Path.cwd()))

from config import (
    DATA_PATH, JD_FILE_PATH, OUTPUT_PATH, 
    RBB_SHEET, DIGITAL_SHEET, 
    COL_CONFIG, START_ROW, WEIGHT_THRESHOLD
)
from bsc_loader import BSCLoader
print("🚀 Starting BSC processing...")

loader = BSCLoader(DATA_PATH, config=COL_CONFIG)

print("📂 Loading sheets...")
loader.load_separately(RBB_SHEET, DIGITAL_SHEET)

print("🧹 Cleaning RBB...")
rbb_df = loader.clean_rbb(start_row=START_ROW)
print(rbb_df.head())

print("🧹 Cleaning Digital...")
digital_df = loader.clean_digital(start_row=START_ROW)
print(digital_df.head())

print("🔗 Merging...")
combined_df = loader.merge_data()
print(combined_df.shape)

print("📄 Converting to documents...")
documents = loader.to_documents()
print(f"Generated {len(documents)} documents")

rbb_df.to_csv(OUTPUT_PATH / "rbb_cleaned.csv", index=False)
digital_df.to_csv(OUTPUT_PATH / "digital_cleaned.csv", index=False)
combined_df.to_csv(OUTPUT_PATH / "bsc_merged_complete.csv", index=False)

output_file = OUTPUT_PATH / "bsc_documents.json"



with open(output_file, "w", encoding="utf-8") as f:
    json.dump(documents, f, indent=2, ensure_ascii=False)

print(f"✅ Documents saved at: {output_file}")
