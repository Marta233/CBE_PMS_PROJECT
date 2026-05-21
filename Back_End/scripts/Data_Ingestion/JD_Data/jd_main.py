import sys
from pathlib import Path
import pandas as pd
import json

sys.path.insert(0, str(Path(__file__).parent))

from .jd_config import OUTPUT_PATH, RBB_JD_PATH, DIGITAL_JD_PATH, OUTPUT_COLS
from .rbb_loader import RBBLoader
from .digital_loader import DigitalLoader

def run_pipeline() -> tuple[pd.DataFrame, list]:
    """
    Load, combine, save, and return the combined JD dataframe and documents.
    """

    print("=" * 68)
    print("JD DATA INGESTION PIPELINE")
    print("=" * 68)

    # Step 1: load
    rbb_df = RBBLoader(RBB_JD_PATH).load()
    digital_df = DigitalLoader(DIGITAL_JD_PATH).load()

    # Step 2: combine
    combined = pd.concat([rbb_df, digital_df], ignore_index=True)

    combined = combined[[c for c in OUTPUT_COLS if c in combined.columns]]

    combined = combined.drop_duplicates(
        subset=["unit", "job_title"],
        keep="first"
    ).reset_index(drop=True)

    # Step 3: save csv
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    rbb_df.to_csv(OUTPUT_PATH / "jd_rbb.csv", index=False)
    digital_df.to_csv(OUTPUT_PATH / "jd_digital.csv", index=False)
    combined.to_csv(OUTPUT_PATH / "jd_combined.csv", index=False)

    # Step 4: responsibilities long format
    long_rows = []

    for _, row in combined.iterrows():
        responsibilities = row.get("responsibilities")

        if not isinstance(responsibilities, list):
            responsibilities = []

        for idx, resp in enumerate(responsibilities, start=1):
            long_rows.append({
                "source": row["source"],
                "division": row["division"],
                "unit": row["unit"],
                "department": row.get("department"),
                "department": row["department"],
                "job_title": row["job_title"],
                "job_grade": row.get("job_grade"),
                "job_objective": row.get("job_objective"),
                "responsibility_no": idx,
                "responsibility": resp,
            })

    pd.DataFrame(long_rows).to_csv(
        OUTPUT_PATH / "jd_responsibilities.csv",
        index=False
    )

    # Step 5: JSON documents
    documents = []

    for _, row in combined.iterrows():
        responsibilities = row.get("responsibilities")

        if isinstance(responsibilities, list):
            resp_text = ", ".join(responsibilities)
        else:
            resp_text = str(responsibilities) if pd.notna(responsibilities) else ""

        text = f"""
Division: {row['division']}
Unit: {row['unit']}
Department: {row['department']}
Job Title: {row['job_title']}
Job Grade: {row.get('job_grade', 'N/A')}
Job Objective: {row.get('job_objective', 'N/A')}
Responsibilities: {resp_text}
"""

        metadata = {
            "source": row["source"],
            "division": row["division"],
            "department": row["department"],
        }

        documents.append({
            "text": text.strip(),
            "metadata": metadata
        })

    output_file = OUTPUT_PATH / "jd_documents.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(documents, f, indent=2, ensure_ascii=False)

    print(f"✅ Saved JSON: {output_file}")
    print(f"✅ Generated {len(documents)} documents")

    return combined, documents


if __name__ == "__main__":
    combined_df, docs = run_pipeline()