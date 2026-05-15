from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]  # CBE_PMS_PROJECT/scripts

PROJECT_ROOT = BASE_DIR.parent

DATA_PATH = PROJECT_ROOT / "Data" / "raw" / "Bsc_of_DB_and_RBB_divisions.xlsx"

RBB_JD_PATH = PROJECT_ROOT / "Data" / "raw" / "RBB_JD.docx"

DIGITAL_JD_PATH = PROJECT_ROOT / "Data" / "raw" / "Digital Banking JD.pdf"

LOS_DATA_PATH = PROJECT_ROOT / "Data" / "raw" / "Data_Processed.xlsx"

OUTPUT_PATH = PROJECT_ROOT / "Data" / "processed"