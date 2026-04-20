# main.py
"""Main execution script for BSC and JD data processing"""

from pathlib import Path
import sys
import argparse

# Add current directory to path
sys.path.insert(0, str(Path.cwd()))

from config import (
    DATA_PATH, JD_FILE_PATH, OUTPUT_PATH, 
    RBB_SHEET, DIGITAL_SHEET, 
    COL_CONFIG, START_ROW, WEIGHT_THRESHOLD
)
from bsc_loader import BSCLoader
from jd_loader import JDLoader
"""Process JD data only"""
print("="*80)
print("JD DATA PROCESSING PIPELINE")
print("="*80)

# Initialize loader
print("\n[1/3] Initializing JD Loader...")
loader = JDLoader(JD_FILE_PATH)

# Load document
print("\n[2/3] Loading JD document...")
raw_df = loader.load_document()
print(f"   Raw shape: {raw_df.shape}")

# Clean data
print("\n[3/3] Cleaning JD data...")
clean_df = loader.clean_data()
print(f"   Clean shape: {clean_df.shape}")

# Save outputs
print("\n" + "="*80)
print("SAVING JD OUTPUTS")
print("="*80)

loader.save_to_csv(OUTPUT_PATH)
loader.save_responsibilities_expanded(OUTPUT_PATH)

print(f"✅ Saved JD data to {OUTPUT_PATH}")
print(f"   - jd_processed_data.csv ({len(clean_df)} rows)")
print(f"   - jd_responsibilities_expanded.csv")

