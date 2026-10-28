# los_loader.py
"""LOS Data Loader Module"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import logging
import re

try:                                    # package import (API) or flat import (scripts)
    from common import registry
except ImportError:                     # pragma: no cover
    from ..common import registry       # type: ignore

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class LOSLoader:
    """
    Load and process LOS data from Excel - ONE loader for every division.

    Each sheet of the workbook is one DEPARTMENT. The department's division is looked up in the
    organisation registry (common/org_registry.json), so a new division or department is
    onboarded by editing the registry, not this code. The sheet name is kept as written;
    finalize() maps it to the canonical department name and reports the rename.
    """

    def __init__(self, file_path: Path, config: Dict = None):

        self.file_path = Path(file_path)
        self.config = config or {}

        self.raw_sheets = {}
        self.clean_sheets = {}
        self.combined_data = None

    def load_all_sheets(self) -> Dict[str, pd.DataFrame]:
        """
        Load all sheets dynamically
        """

        logger.info(f"\n📂 Loading LOS file: {self.file_path.name}")

        try:

            # IMPORTANT: automatically closes workbook
            with pd.ExcelFile(self.file_path) as excel_file:

                logger.info(
                    f"  ✓ Found {len(excel_file.sheet_names)} sheets"
                )

                for sheet_name in excel_file.sheet_names:

                    try:

                        df = pd.read_excel(
                            excel_file,
                            sheet_name=sheet_name,
                            header=None
                        )

                        self.raw_sheets[sheet_name] = df

                        logger.info(
                            f"    ✓ Loaded '{sheet_name}': {len(df)} rows"
                        )

                    except Exception as e:

                        logger.error(
                            f"    ✗ Error loading '{sheet_name}': {e}"
                        )

        except Exception as e:

            logger.error(f"❌ Failed loading Excel file: {e}")

        return self.raw_sheets

    def _clean_text(self, value) -> Optional[str]:
        """
        Clean text values
        """

        if pd.isna(value):
            return None

        value = str(value).strip()

        if value == "" or value.lower() == "nan":
            return None

        return value

    # Sheet names that say nothing about the department ("Sheet1", "Data", "LOS", a year...).
    _GENERIC_SHEET = re.compile(r"^\s*(sheet\s*\d*|data|los|objectives?|[\d./\-_\s]*)\s*$", re.IGNORECASE)

    @classmethod
    def sheet_scope(cls, sheet_name: str) -> Tuple[str, str]:
        """(division, department) for a sheet. The division comes from the registry (the
        division that owns the department named by the sheet). Blank division: the upload form
        may supply it, otherwise finalize() rejects the rows with a clear message. A sheet with
        a generic name ("Sheet1") gives a blank department, so a workbook of ONE department can
        take it from the upload form."""
        department = str(sheet_name).strip()
        if cls._GENERIC_SHEET.match(department):
            return "", ""
        known = registry.find_department(department)
        division = registry.division_of_department(known) if known else ""
        return division or "", department

    def clean_sheet(
        self,
        sheet_name: str,
        start_row: int = 1
    ) -> pd.DataFrame:
        """
        Clean single LOS sheet
        """

        if sheet_name not in self.raw_sheets:

            logger.error(
                f"❌ Sheet '{sheet_name}' not loaded"
            )

            return pd.DataFrame()

        logger.info(f"\n📋 Cleaning sheet: {sheet_name}")

        raw_df = self.raw_sheets[sheet_name]
        sheet_division, sheet_department = self.sheet_scope(sheet_name)

        data_rows = []

        current_perspective = None
        current_strategic_objective = None
        current_division_objective = None
        current_department_objective = None

        # Config columns
        col_perspective = self.config.get(
            'perspective_col', 0
        )

        col_strategic = self.config.get(
            'strategic_obj_col', 1
        )

        col_division = self.config.get(
            'division_obj_col', 2
        )

        col_department = self.config.get(
            'department_obj_col', 3
        )

        col_unit = self.config.get(
            'unit_obj_col', 4
        )

        for idx in range(start_row, len(raw_df)):

            row = raw_df.iloc[idx]

            # Perspective
            perspective = (
                row.iloc[col_perspective]
                if len(row) > col_perspective else None
            )

            cleaned_perspective = self._clean_text(
                perspective
            )

            if cleaned_perspective:
                current_perspective = cleaned_perspective

            # Strategic Objective
            strategic_obj = (
                row.iloc[col_strategic]
                if len(row) > col_strategic else None
            )

            cleaned_strategic = self._clean_text(
                strategic_obj
            )

            if cleaned_strategic:
                current_strategic_objective = cleaned_strategic

            # Division Objective
            division_obj = (
                row.iloc[col_division]
                if len(row) > col_division else None
            )

            cleaned_division = self._clean_text(
                division_obj
            )

            if cleaned_division:
                current_division_objective = cleaned_division

            # Department Objective
            department_obj = (
                row.iloc[col_department]
                if len(row) > col_department else None
            )

            cleaned_department = self._clean_text(
                department_obj
            )

            if cleaned_department:
                current_department_objective = cleaned_department

            # Unit Objective
            unit_obj = (
                row.iloc[col_unit]
                if len(row) > col_unit else None
            )

            cleaned_unit = self._clean_text(unit_obj)

            if not cleaned_unit:
                continue

            data_rows.append({

                "division": sheet_division,

                "department": sheet_department,

                "perspective": current_perspective,

                "strategic_objective":
                    current_strategic_objective,

                "division_objective":
                    current_division_objective,

                "department_objective":
                    current_department_objective,

                "unit_objective":
                    cleaned_unit
            })

        cleaned_df = pd.DataFrame(data_rows, columns=[
            "division", "department", "perspective", "strategic_objective",
            "division_objective", "department_objective", "unit_objective"])

        cleaned_df = cleaned_df.drop_duplicates()

        self.clean_sheets[sheet_name] = cleaned_df

        logger.info(
            f"  ✅ Cleaned {len(cleaned_df)} rows"
        )

        return cleaned_df

    def clean_all_sheets(
        self,
        start_row: int = 1
    ) -> Dict[str, pd.DataFrame]:
        """
        Clean all sheets
        """

        if not self.raw_sheets:

            logger.error("❌ No sheets loaded yet")

            return {}

        logger.info("\n🧹 Cleaning all LOS sheets...")

        for sheet_name in self.raw_sheets.keys():

            self.clean_sheet(
                sheet_name=sheet_name,
                start_row=start_row
            )

        return self.clean_sheets

    def merge_data(self) -> pd.DataFrame:
        """
        Merge all LOS sheets
        """

        if not self.clean_sheets:

            self.clean_all_sheets()

        logger.info("\n🔗 Merging LOS sheets...")

        all_dataframes = [df for df in self.clean_sheets.values() if not df.empty]

        self.combined_data = pd.concat(
            all_dataframes,
            ignore_index=True
        ) if all_dataframes else pd.DataFrame(columns=[
            "division", "department", "perspective", "strategic_objective",
            "division_objective", "department_objective", "unit_objective"])

        logger.info(
            f"  ✅ Merged {len(self.combined_data)} rows"
        )

        logger.info(
            f"     - Departments: {len(self.clean_sheets)}"
        )

        return self.combined_data

    def to_documents(self) -> List[Dict[str, Any]]:
        """
        Convert LOS into embedding-ready documents.

        Text excludes Division/Department — those are already stated in
        the employee's own query profile (Division/Department/Unit/Job
        Title/Job Grade), so repeating them on every single LOS row is
        pure redundant token cost with zero new information. Division and
        Department stay in `metadata` below, which is what _filter_los_
        hierarchical() actually uses for department/unit matching —
        metadata is for retrieval only, never shown to the model directly.
        """

        if self.combined_data is None:

            self.merge_data()

        documents = []

        for _, row in self.combined_data.iterrows():

            text = f"""
            Perspective: {row['perspective']}
            Strategic Objective: {row['strategic_objective']}
            Division Objective: {row['division_objective']}
            Department Objective: {row['department_objective']}
            Unit Objective: {row['unit_objective']}
            """

            metadata = {

                "source": "LOS",

                "division": row["division"],

                "department": row["department"],

            }

            documents.append({
                "text": text.strip(),
                "metadata": metadata
            })

        logger.info(
            f"\n📄 Created {len(documents)} LOS documents"
        )

        return documents