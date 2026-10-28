# bsc_loader.py
"""
BSC Data Loader - ONE loader for every division.

A BSC workbook may hold several divisions (one sheet each) or just one. The division of a sheet is
found through the organisation registry (e.g. " RBB 2025.2026" -> RBB, "Digital 2025.2026" ->
Digital Banking). All sheets are read with the same rules, so a new division is onboarded by
adding it to common/org_registry.json - no new loader, no code change.

If the workbook also holds older years (e.g. 'RBB 2024.2025'), only the latest year per division
is read. Rules for a sheet (the same for all divisions):
  * the Strategic Objective cell may be merged: it carries down to the rows below it
  * a row needs a KPI to count; the "Major - KPI" sub-header row is skipped
  * reading stops at a row whose Strategic Objective contains TOTAL
"""
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

try:                                    # package import (API) or flat import (scripts)
    from common import registry
except ImportError:                     # pragma: no cover
    from ..common import registry       # type: ignore

logger = logging.getLogger(__name__)


class BSCLoader:
    """Load and process BSC data from an Excel workbook (any number of divisions)."""

    def __init__(self, file_path: Path, config: Dict = None):
        self.file_path = Path(file_path)
        self.config = config or {}
        self.raw_sheets: Dict[str, pd.DataFrame] = {}
        self.clean_sheets: Dict[str, pd.DataFrame] = {}
        self.sheet_divisions: Dict[str, str] = {}
        self.skipped_sheets: List[str] = []
        self.combined_data: Optional[pd.DataFrame] = None

    # ------------------------------------------------------------------ load
    def load_all_sheets(self) -> Dict[str, pd.DataFrame]:
        logger.info(f"\n📂 Loading file: {self.file_path.name}")
        with pd.ExcelFile(self.file_path) as excel_file:          # closes the workbook
            for sheet_name in excel_file.sheet_names:
                self.raw_sheets[sheet_name] = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
                logger.info(f"  ✓ Loaded '{sheet_name}': {len(self.raw_sheets[sheet_name])} rows")
        return self.raw_sheets

    @staticmethod
    def _sheet_year(name: str) -> int:
        """Start year in a sheet name: ' RBB 2025.2026' -> 2025, 'Digital 2024/25' -> 2024.
        -1 when the name carries no year."""
        m = re.search(r"(20\d{2})\s*[./\-_]\s*(?:20)?\d{2}", name)
        return int(m.group(1)) if m else -1

    @staticmethod
    def _header_row(df: pd.DataFrame) -> Optional[int]:
        """Row of the table header ('Strategic Objectives' in the first column), if there is one."""
        for r in range(min(len(df), 30)):
            first = df.iat[r, 0] if df.shape[1] else None
            if isinstance(first, str) and "strategic" in first.lower():
                return r
        return None

    def _division_of_sheet(self, sheet_name: str) -> str:
        """
        Division of one sheet, taken from the CONTENT first, so a sheet called "Sheet1" or
        "2025.2026" works:
          1. the title lines above the table header ("Digital Banking Division")
          2. the sheet name
          3. the file name
        '' when none of them names a known division (the upload form may then supply it).
        KPI rows are never used as a hint: they can mention another division's words.
        """
        df = self.raw_sheets[sheet_name]
        header = self._header_row(df)
        for r in range(header if header is not None else min(len(df), 8)):
            for v in df.iloc[r]:
                if isinstance(v, str):
                    found = registry.find_division(v)
                    if found:
                        return found
        return registry.find_division(sheet_name) or registry.find_division(self.file_path.stem) or ""

    def _assign_divisions(self) -> None:
        """
        Pick the sheets to read and give each its division. Works for a workbook that holds
        several divisions (one sheet each) AND for a workbook of a single division whose sheets
        are named only by year, or not named at all.

        * Division of a sheet: the title lines above the table (content), then sheet name, then file name.
        * A workbook usually keeps older years next to the current one. For each division the
          sheet with the LATEST year in its name is read; the others are ignored.
        * Sheets that name no division (notes, summaries) are ignored when at least one sheet
          does. If NO sheet names a division, the latest-year sheet is read with a blank
          division: the upload form supplies it, otherwise the document is rejected with a
          clear message ("division is required").
        """
        found = {name: self._division_of_sheet(name) for name in self.raw_sheets}
        groups: Dict[str, List[str]] = {}
        for name, div in found.items():
            groups.setdefault(div, []).append(name)
        if any(groups):                                  # at least one named division
            groups = {d: n for d, n in groups.items() if d}
        chosen = {}
        for div, names in groups.items():
            chosen[max(names, key=lambda n: self._sheet_year(n))] = div      # first of equals wins
        self.sheet_divisions = {n: chosen[n] for n in self.raw_sheets if n in chosen}
        self.skipped_sheets = [n for n in self.raw_sheets if n not in chosen]
        for n in self.skipped_sheets:
            why = "older year or duplicate of a sheet already read" if found.get(n) in groups else "names no known division"
            logger.warning(f"  ⚠️ Sheet '{n}' ignored ({why})")
        if "" in chosen.values():
            logger.warning("  ⚠️ No sheet names a division - division left blank (the upload form can supply it)")

    # ----------------------------------------------------------------- clean
    @staticmethod
    def _clean_numeric(value) -> Optional[float]:
        if pd.isna(value):
            return None
        if isinstance(value, (int, float)):
            return float(value) if not np.isnan(value) else None
        if isinstance(value, str):
            cleaned = re.sub(r'[^0-9.]', '', value.strip())
            try:
                return float(cleaned) if cleaned else None
            except ValueError:
                return None
        return None

    @staticmethod
    def _text(row, col) -> str:
        if len(row) <= col:
            return ""
        v = row.iloc[col]
        return "" if pd.isna(v) else str(v).strip()

    def clean_sheet(self, sheet_name: str, start_row: int = 1) -> pd.DataFrame:
        raw = self.raw_sheets[sheet_name]
        division = self.sheet_divisions.get(sheet_name, "")
        c = self.config
        col_so, col_kpi = c.get('strategic_obj_col', 0), c.get('kpi_col', 1)
        col_ms, col_w, col_plan = c.get('measurement_col', 2), c.get('weight_col', 3), c.get('plan_col', 9)

        header = self._header_row(raw)
        first_row = header + 1 if header is not None else start_row      # data begins under the header
        rows, current = [], None
        for idx in range(first_row, len(raw)):
            row = raw.iloc[idx]
            strategic = self._text(row, col_so)
            if strategic:
                if 'TOTAL' in strategic.upper():
                    break
                current = strategic                      # merged cell: carries down
            kpi = self._text(row, col_kpi)
            if not kpi or 'Major - KPI' in kpi or current is None:
                continue
            plan = row.iloc[col_plan] if len(row) > col_plan else None
            rows.append({
                'division': division,
                'strategic_objective': current,
                'kpi': kpi,
                'measurement': self._text(row, col_ms),
                'weight': self._clean_numeric(row.iloc[col_w] if len(row) > col_w else None) or 0,
                'plan': plan if pd.notna(plan) else None,
            })
        df = pd.DataFrame(rows)
        self.clean_sheets[sheet_name] = df
        logger.info(f"  ✅ '{sheet_name}' ({division or 'division unknown'}): {len(df)} KPIs")
        return df

    def clean_all_sheets(self, start_row: int = 1) -> Dict[str, pd.DataFrame]:
        if not self.raw_sheets:
            self.load_all_sheets()
        if not self.sheet_divisions:
            self._assign_divisions()
        for name in self.sheet_divisions:
            self.clean_sheet(name, start_row)
        return self.clean_sheets

    def merge_data(self) -> pd.DataFrame:
        if not self.clean_sheets:
            self.clean_all_sheets()
        frames = [df for df in self.clean_sheets.values() if not df.empty]
        self.combined_data = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
            columns=['division', 'strategic_objective', 'kpi', 'measurement', 'weight', 'plan'])
        logger.info(f"\n🔗 Merged {len(self.combined_data)} KPIs from {len(frames)} division sheet(s)")
        return self.combined_data

    # ------------------------------------------------------------- documents
    def to_documents(self) -> list:
        """
        Text is ONLY Strategic Objective + KPI. Measurement/Target/weight are division-wide
        figures, so they stay in `metadata` (weight is read from metadata by extractor.py's
        _retrieve_bsc() for grade-band scoring).
        """
        if self.combined_data is None:
            self.merge_data()
        documents = []
        for _, row in self.combined_data.iterrows():
            text = f"""
            Strategic Objective: {row['strategic_objective']}
            KPI: {row['kpi']}
            """
            documents.append({
                "text": text.strip(),
                "metadata": {
                    "source": "BSC",
                    "division": row["division"],
                    "kpi": row["kpi"],
                    "measurement": row["measurement"],
                    "target": row["plan"],
                    "weight": row["weight"],
                },
            })
        return documents