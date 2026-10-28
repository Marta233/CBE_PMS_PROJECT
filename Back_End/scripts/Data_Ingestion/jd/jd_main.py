import pandas as pd
import json
from pathlib import Path

from .jd_config import OUTPUT_PATH, JD_FILES, OUTPUT_COLS
from .jd_loader import JDLoader
from . import _df_to_documents


def run_pipeline() -> tuple[pd.DataFrame, list]:
    print("=" * 68)
    print("JD DATA INGESTION PIPELINE")
    print("=" * 68)

    frames = []
    for path in JD_FILES:
        if not Path(path).exists():
            print(f"⚠️  Skipping missing file: {path}")
            continue
        frames.append(JDLoader(path).load())
    if not frames:
        print("⚠️  No JD files found")
        return pd.DataFrame(), []

    combined = pd.concat(frames, ignore_index=True)

    # ── Dedup key: division + unit + job_title + job_grade + reports_to
    #  Grade: the same title can exist at two grades in one unit.
    #  reports_to: many units share generic titles but report to different team leaders.
    dedup_cols = [c for c in ["division", "unit", "job_title", "job_grade", "reports_to"]
                  if c in combined.columns]
    before = len(combined)
    combined = combined.drop_duplicates(subset=dedup_cols, keep="first").reset_index(drop=True)
    print(f"\n🔁 Dedup: {before} → {len(combined)} records (removed {before - len(combined)} true duplicate(s))")

    combined = combined[[c for c in OUTPUT_COLS if c in combined.columns]]
    print(f"\n📊 Final: {len(combined)} unique JDs from {len(frames)} file(s)")

    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
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

    documents = _df_to_documents(combined)
    output_file = OUTPUT_PATH / "jd_documents.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(documents, f, indent=2, ensure_ascii=False)

    print(f"✅ Saved JSON: {output_file}")
    print(f"✅ Generated {len(documents)} documents")
    return combined, documents


if __name__ == "__main__":
    combined_df, docs = run_pipeline()
