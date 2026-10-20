"""
Export generated objectives CSV via the same API path as Performance Planning.

Mirrors frontend callAPI + downloadCSV:
  POST /api/generate  (division, department, unit, job_title, job_grade, num_objectives)
  poll GET /api/jobs/{id} when 202
  write CSV in the same layout as downloadCSV()

Job grade is sent as "" (empty), same as leaving the UI Job Grade field blank.

Usage (from Back_End/, with uvicorn running):
    python -m tests.scripts.export_mobile_money_objectives --suite mobile_money
    python -m tests.scripts.export_mobile_money_objectives --suite merchant_agent
    python -m tests.scripts.export_mobile_money_objectives --suite merchant_agent --only "Digital Banking Officer"
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from io import StringIO
from pathlib import Path

_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"
DEFAULT_API_URL = "http://127.0.0.1:8000"
POLL_INTERVAL_SEC = 2.0
POLL_TIMEOUT_SEC = 3600.0  # long-running LLM; no UI gateway timeout

# Same fields the UI generate form uses (job_grade left blank like an empty input).
SUITES: dict[str, list[dict]] = {
    "mobile_money": [
        {
            "division": "Digital Banking",
            "department": "Mobile Money",
            "unit": "Mobile Money Business",
            "job_title": "Associate Digital Banking Officer I",
            "job_grade": "",
            "num_objectives": 5,
        },
        {
            "division": "Digital Banking",
            "department": "Mobile Money",
            "unit": "Mobile Money Business",
            "job_title": "Associate Digital Banking Officer II",
            "job_grade": "",
            "num_objectives": 5,
        },
        {
            "division": "Digital Banking",
            "department": "Mobile Money",
            "unit": "Mobile Money Business",
            "job_title": "Junior Officer I",
            "job_grade": "",
            "num_objectives": 5,
        },
    ],
    "merchant_agent": [
        {
            "division": "Digital Banking",
            "department": "Merchant and Agent Management",
            "unit": "Agent Management",
            "job_title": "Associate Digital Banking Officer I",
            "job_grade": "",
            "num_objectives": 5,
        },
        {
            "division": "Digital Banking",
            "department": "Merchant and Agent Management",
            "unit": "Digital Partners Relationship",
            "job_title": "Digital Banking Officer",
            "job_grade": "",
            "num_objectives": 5,
        },
        {
            "division": "Digital Banking",
            "department": "Merchant and Agent Management",
            "unit": "Merchant Management",
            "job_title": "Team Leader Mobile Money Management",
            "job_grade": "",
            "num_objectives": 5,
        },
        {
            "division": "Digital Banking",
            "department": "Merchant and Agent Management",
            "unit": "Agent Management",
            "job_title": "Senior Digital Banking Officer",
            "job_grade": "",
            "num_objectives": 5,
        },
    ],
}

# Back-compat for tests that import CASES
CASES = SUITES["mobile_money"]

# Matches APPRAISAL_RATINGS titles in PerformancePlanning.tsx
APPRAISAL_HEADERS = [
    "Rating 5 - Outstanding",
    "Rating 4 - Exceeds",
    "Rating 3 - Meets",
    "Rating 2 - Partially",
    "Rating 1 - Unsatisfactory",
]


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")


def _http_json(method: str, url: str, body: dict | None = None, timeout: float = 120.0) -> tuple[int, dict]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"detail": raw or str(exc)}
        return exc.code, payload


def call_generate_api(api_url: str, case: dict) -> dict:
    """Same contract as frontend callAPI()."""
    payload = {
        "division": case["division"],
        "department": case["department"],
        "unit": case["unit"],
        "job_title": case["job_title"],
        "job_grade": case.get("job_grade", ""),
        "num_objectives": case["num_objectives"],
    }
    status, data = _http_json("POST", f"{api_url.rstrip('/')}/api/generate", payload, timeout=120.0)

    if status == 202:
        poll_url = data.get("poll_url") or f"/api/jobs/{data.get('job_id')}"
        if not poll_url.startswith("http"):
            poll_url = f"{api_url.rstrip('/')}{poll_url}"
        print(f"  Queued job {data.get('job_id')} — polling {poll_url}")
        return _poll_job(poll_url)

    if status != 200:
        raise RuntimeError(f"POST /api/generate failed ({status}): {data}")

    return data


def _poll_job(poll_url: str) -> dict:
    deadline = time.monotonic() + POLL_TIMEOUT_SEC
    last_stage = None
    while time.monotonic() < deadline:
        try:
            status, data = _http_json("GET", poll_url, timeout=30.0)
        except TimeoutError:
            print("  Poll timed out — retrying …")
            time.sleep(POLL_INTERVAL_SEC)
            continue
        except urllib.error.URLError as exc:
            print(f"  Poll connection error ({exc}) — retrying …")
            time.sleep(POLL_INTERVAL_SEC)
            continue

        if status != 200:
            raise RuntimeError(f"GET job status failed ({status}): {data}")

        job_status = data.get("status")
        progress = data.get("progress") or {}
        stage = progress.get("stage")
        if stage and stage != last_stage:
            print(f"  Progress: {stage} — {progress.get('message') or ''}")
            last_stage = stage

        if job_status == "completed":
            result = data.get("result")
            if not result:
                raise RuntimeError(f"Job completed with empty result: {data}")
            return result
        if job_status == "failed":
            raise RuntimeError(
                f"Generation failed: {data.get('error') or data.get('detail') or data}"
            )

        time.sleep(POLL_INTERVAL_SEC)

    raise TimeoutError(f"Timed out after {POLL_TIMEOUT_SEC:.0f}s polling {poll_url}")


def objectives_to_csv(result: dict, case: dict) -> str:
    """Mirror frontend downloadCSV objective + appraisal sections (planning meta only)."""
    objectives = result.get("objectives") or []
    now = datetime.now()
    date_part = now.strftime("%d/%m/%Y")
    time_part = now.strftime("%H:%M:%S")

    obj_cols = 6
    appraisal_cols = 7

    def pad(cells: list, width: int) -> list:
        out = list(cells)
        while len(out) < width:
            out.append("")
        return out[:width]

    lines: list[list] = []
    # meta block — same ObjectiveSet fields the UI writes (not job grade / grade band)
    lines.append(pad(["Division", case["division"]], obj_cols))
    lines.append(pad(["Department", case["department"]], obj_cols))
    lines.append(pad(["Unit", case["unit"]], obj_cols))
    lines.append(pad(["Job Title", case["job_title"]], obj_cols))
    lines.append(pad(["Generated", date_part, time_part], obj_cols))
    lines.append(pad([""], obj_cols))

    lines.append(pad(["#", "Objective", "Measure", "Target", "Weight (%)", "Category"], obj_cols))
    for i, obj in enumerate(objectives, 1):
        lines.append(
            pad(
                [
                    i,
                    obj.get("objective", ""),
                    obj.get("measure", ""),
                    obj.get("target", ""),
                    obj.get("weight_percent", ""),
                    obj.get("category", ""),
                ],
                obj_cols,
            )
        )

    lines.append(pad([""], obj_cols))
    lines.append(pad(["Appraisal"], obj_cols))
    lines.append(pad(["#", "Objective", *APPRAISAL_HEADERS], appraisal_cols))
    for i, obj in enumerate(objectives, 1):
        a = obj.get("appraisal_logic") or {}
        lines.append(
            pad(
                [
                    i,
                    obj.get("objective", ""),
                    a.get("rating_5", ""),
                    a.get("rating_4", ""),
                    a.get("rating_3", ""),
                    a.get("rating_2", ""),
                    a.get("rating_1", ""),
                ],
                appraisal_cols,
            )
        )

    buf = StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    for row in lines:
        writer.writerow(row)
    return "\ufeff" + buf.getvalue()


def run_case(case: dict, api_url: str) -> Path:
    title = case["job_title"]
    unit = case["unit"]
    print("\n" + "=" * 72)
    print(f"Generating via API: {unit} / {title}  ({case['num_objectives']} objectives)")
    print("=" * 72)

    result = call_generate_api(api_url, case)
    objectives = result.get("objectives") or []
    print(f"  Objectives : {len(objectives)}")
    print(f"  Total weight: {result.get('total_weight')}%")

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{_slug(unit)}_{_slug(title)}"
    csv_path = _OUTPUT_DIR / f"{stem}.csv"
    json_path = _OUTPUT_DIR / f"{stem}.json"

    csv_path.write_text(objectives_to_csv(result, case), encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "case": case,
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "api_response": result,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"  CSV  -> {csv_path}")
    print(f"  JSON -> {json_path}")
    return csv_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help=f"Backend base URL (default: {DEFAULT_API_URL})",
    )
    parser.add_argument(
        "--suite",
        choices=sorted(SUITES.keys()),
        default="mobile_money",
        help="Which case suite to run (default: mobile_money).",
    )
    parser.add_argument(
        "--only",
        action="append",
        dest="only",
        help="Run only matching job title(s).",
    )
    args = parser.parse_args(argv)

    cases = list(SUITES[args.suite])
    if args.only:
        wanted = {t.lower() for t in args.only}
        cases = [c for c in cases if c["job_title"].lower() in wanted]
        if not cases:
            print(f"No cases matched --only {args.only}", file=sys.stderr)
            return 1

    print(f"API: {args.api_url}")
    print(f"Suite: {args.suite} ({len(cases)} case(s))")
    print(f"Output folder: {_OUTPUT_DIR}")
    written: list[Path] = []
    for case in cases:
        written.append(run_case(case, args.api_url))

    print("\n" + "=" * 72)
    print(f"Done. {len(written)} CSV file(s) in {_OUTPUT_DIR}")
    for p in written:
        print(f"  - {p.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
