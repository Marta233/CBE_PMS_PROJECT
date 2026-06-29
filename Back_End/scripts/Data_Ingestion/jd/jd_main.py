import pandas as pd
import json
from pathlib import Path

from .jd_config import OUTPUT_PATH, RBB_JD_PATH, DIGITAL_JD_PATH, OUTPUT_COLS
from .rbb_loader import RBBLoader
from .digital_loader import DigitalLoader


def run_pipeline() -> tuple[pd.DataFrame, list]:
    print("=" * 68)
    print("JD DATA INGESTION PIPELINE")
    print("=" * 68)

    rbb_df     = RBBLoader(RBB_JD_PATH).load()
    digital_df = DigitalLoader(DIGITAL_JD_PATH).load()

    combined = pd.concat([rbb_df, digital_df], ignore_index=True)

    # ── Dedup key: division + unit + job_title + job_grade + reports_to
    #
    #  Why grade?  The PDF has roles like "Banking Operation Officer" that
    #  appear at both grade 9 and grade 10 within the same unit, with the
    #  same reports-to.  Without grade in the key, one gets silently dropped.
    #
    #  Why reports_to?  Many units share the same generic titles
    #  ("Senior Digital Banking Officer") but each team is distinct because
    #  it reports to a different team leader.
    #
    dedup_cols = [c for c in ["division", "unit", "job_title", "job_grade", "reports_to"]
                  if c in combined.columns]

    before = len(combined)
    combined = combined.drop_duplicates(subset=dedup_cols, keep="first").reset_index(drop=True)
    after = len(combined)
    print(f"\n🔁 Dedup: {before} → {after} records (removed {before - after} true duplicate(s))")

    # Drop internal dedup column before saving
    out_cols = [c for c in OUTPUT_COLS if c in combined.columns]
    combined = combined[out_cols]

    print(f"\n📊 Final: {len(rbb_df)} RBB + {len(digital_df)} Digital = {len(combined)} unique JDs")

    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    rbb_df.to_csv(OUTPUT_PATH / "jd_rbb.csv", index=False)
    digital_df.to_csv(OUTPUT_PATH / "jd_digital.csv", index=False)
    combined.to_csv(OUTPUT_PATH / "jd_combined.csv", index=False)

    long_rows = []
    for _, row in combined.iterrows():
        responsibilities = row.get("responsibilities")
        if not isinstance(responsibilities, list):
            responsibilities = []
        for idx, resp in enumerate(responsibilities, start=1):
            long_rows.append({
                "source":            row["source"],
                "division":          row["division"],
                "unit":              row.get("unit", ""),
                "department":        row.get("department", ""),
                "job_title":         row["job_title"],
                "job_grade":         row.get("job_grade"),
                "job_objective":     row.get("job_objective"),
                "responsibility_no": idx,
                "responsibility":    resp,
            })
    pd.DataFrame(long_rows).to_csv(OUTPUT_PATH / "jd_responsibilities.csv", index=False)

    documents = []
    for _, row in combined.iterrows():
        responsibilities = row.get("responsibilities")
        if isinstance(responsibilities, list):
            resp_text = ", ".join(responsibilities)
        else:
            resp_text = str(responsibilities) if pd.notna(responsibilities) else ""

        text = (
            f"Division: {row['division']}\n"
            f"Unit: {row.get('unit', '')}\n"
            f"Department: {row.get('department', '')}\n"
            f"Job Title: {row['job_title']}\n"
            f"Job Grade: {row.get('job_grade', 'N/A')}\n"
            f"Job Objective: {row.get('job_objective', 'N/A')}\n"
            f"Responsibilities: {resp_text}"
        )
        metadata = {
            "source":     row["source"],
            "division":   row["division"],
            "department": row.get("department", ""),
            "unit":       row.get("unit", ""),
            "job_title":  row["job_title"],
            "job_grade":  str(row.get("job_grade", "")),
        }
        documents.append({"text": text.strip(), "metadata": metadata})

    output_file = OUTPUT_PATH / "jd_documents.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(documents, f, indent=2, ensure_ascii=False)

    print(f"✅ Saved JSON: {output_file}")
    print(f"✅ Generated {len(documents)} documents")
    return combined, documents


if __name__ == "__main__":
    combined_df, docs = run_pipeline()