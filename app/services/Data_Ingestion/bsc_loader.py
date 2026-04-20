# bsc_loader.py
"""BSC Data Loader Module"""
import pandas as pd
import numpy as np
import re
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)
class BSCLoader:
    """Load and process BSC data from Excel"""
    
    def __init__(self, file_path: Path, config: Dict = None):
        """
        Initialize BSC Loader
        
        Args:
            file_path: Path to Excel file
            config: Configuration dictionary with column mappings
        """
        self.file_path = Path(file_path)
        self.config = config or {}
        self.rbb_raw = None
        self.digital_raw = None
        self.rbb_clean = None
        self.digital_clean = None
        self.combined_data = None
        
    def load_separately(self, rbb_sheet: str, digital_sheet: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Load RBB and Digital sheets separately
        
        Args:
            rbb_sheet: Name of RBB sheet
            digital_sheet: Name of Digital sheet
            
        Returns:
            Tuple of (rbb_raw, digital_raw) dataframes
        """
        logger.info(f"\n📂 Loading file: {self.file_path.name}")
        
        # Load RBB sheet
        try:
            self.rbb_raw = pd.read_excel(self.file_path, sheet_name=rbb_sheet, header=None)
            logger.info(f"  ✓ Loaded {rbb_sheet}: {len(self.rbb_raw)} rows")
        except Exception as e:
            logger.error(f"  ✗ Error loading RBB sheet: {e}")
        
        # Load Digital sheet
        try:
            self.digital_raw = pd.read_excel(self.file_path, sheet_name=digital_sheet, header=None)
            logger.info(f"  ✓ Loaded {digital_sheet}: {len(self.digital_raw)} rows")
        except Exception as e:
            logger.error(f"  ✗ Error loading Digital sheet: {e}")
        
        return self.rbb_raw, self.digital_raw
    
    def _clean_numeric(self, value) -> Optional[float]:
        """Clean and convert numeric values"""
        if pd.isna(value):
            return None
        if isinstance(value, (int, float)):
            return float(value) if not np.isnan(value) else None
        if isinstance(value, str):
            cleaned = re.sub(r'[^0-9.]', '', value.strip())
            try:
                return float(cleaned) if cleaned else None
            except:
                return None
        return None
    
    def clean_rbb(self, start_row: int = 2) -> pd.DataFrame:
        """
        Clean and extract RBB data
        
        Args:
            start_row: Row index where data starts
            
        Returns:
            Cleaned RBB dataframe
        """
        if self.rbb_raw is None:
            logger.error("❌ RBB data not loaded yet")
            return pd.DataFrame()
        
        logger.info("\n📋 Cleaning RBB data...")
        data_rows = []
        
        col_strategic = self.config.get('strategic_obj_col', 0)
        col_kpi = self.config.get('kpi_col', 1)
        col_measurement = self.config.get('measurement_col', 2)
        col_weight = self.config.get('weight_col', 3)
        col_plan = self.config.get('plan_col', 9)
        
        for idx in range(start_row, len(self.rbb_raw)):
            row = self.rbb_raw.iloc[idx]
            strategic_obj = row.iloc[col_strategic] if len(row) > col_strategic else None
            
            if pd.isna(strategic_obj) or str(strategic_obj).strip() == '':
                if idx > 20:
                    break
                continue
            
            if 'TOTAL' in str(strategic_obj).upper():
                break
            
            kpi = row.iloc[col_kpi] if len(row) > col_kpi else None
            if pd.isna(kpi) or str(kpi).strip() == '':
                continue
            
            measurement = row.iloc[col_measurement] if len(row) > col_measurement else None
            weight = row.iloc[col_weight] if len(row) > col_weight else None
            plan = row.iloc[col_plan] if len(row) > col_plan else None
            
            weight = self._clean_numeric(weight) or 0
            measurement = str(measurement).strip() if pd.notna(measurement) else ''
            
            data_rows.append({
                'division': 'RBB',
                'strategic_objective': str(strategic_obj).strip(),
                'kpi': str(kpi).strip(),
                'measurement': measurement,
                'weight': weight,
                'plan': plan if pd.notna(plan) else None
            })
        
        self.rbb_clean = pd.DataFrame(data_rows)
        logger.info(f"  ✅ Cleaned {len(self.rbb_clean)} RBB KPIs")
        return self.rbb_clean
    
    def clean_digital(self, start_row: int = 2) -> pd.DataFrame:
        """
        Clean and extract Digital data (handles merged cells)
        
        Args:
            start_row: Row index where data starts
            
        Returns:
            Cleaned Digital dataframe
        """
        if self.digital_raw is None:
            logger.error("❌ Digital data not loaded yet")
            return pd.DataFrame()
        
        logger.info("\n📋 Cleaning Digital data...")
        data_rows = []
        current_strategic_obj = None
        
        col_strategic = self.config.get('strategic_obj_col', 0)
        col_kpi = self.config.get('kpi_col', 1)
        col_measurement = self.config.get('measurement_col', 2)
        col_weight = self.config.get('weight_col', 3)
        col_plan = self.config.get('plan_col', 9)
        
        for idx in range(start_row, len(self.digital_raw)):
            row = self.digital_raw.iloc[idx]
            strategic_obj = row.iloc[col_strategic] if len(row) > col_strategic else None
            
            if pd.notna(strategic_obj) and str(strategic_obj).strip() != '':
                if 'TOTAL' not in str(strategic_obj).upper():
                    current_strategic_obj = str(strategic_obj).strip()
            
            if current_strategic_obj and 'TOTAL' in current_strategic_obj.upper():
                break
            
            kpi = row.iloc[col_kpi] if len(row) > col_kpi else None
            if pd.isna(kpi) or str(kpi).strip() == '':
                continue
            
            if 'Major - KPI' in str(kpi):
                continue
            
            measurement = row.iloc[col_measurement] if len(row) > col_measurement else None
            weight = row.iloc[col_weight] if len(row) > col_weight else None
            plan = row.iloc[col_plan] if len(row) > col_plan else None
            
            weight = self._clean_numeric(weight) or 0
            measurement = str(measurement).strip() if pd.notna(measurement) else ''
            
            if current_strategic_obj:
                data_rows.append({
                    'division': 'Digital',
                    'strategic_objective': current_strategic_obj,
                    'kpi': str(kpi).strip(),
                    'measurement': measurement,
                    'weight': weight,
                    'plan': plan if pd.notna(plan) else None
                })
        
        self.digital_clean = pd.DataFrame(data_rows)
        logger.info(f"  ✅ Cleaned {len(self.digital_clean)} Digital KPIs")
        return self.digital_clean
    def merge_data(self) -> pd.DataFrame:
        """Merge RBB and Digital data into one dataset"""
        if self.rbb_clean is None:
            self.clean_rbb()
        if self.digital_clean is None:
            self.clean_digital()
        
        logger.info("\n🔗 Merging RBB and Digital data...")
        self.combined_data = pd.concat([self.rbb_clean, self.digital_clean], ignore_index=True)
        logger.info(f"  ✅ Merged {len(self.combined_data)} total KPIs")
        logger.info(f"     - RBB: {len(self.rbb_clean)}")
        logger.info(f"     - Digital: {len(self.digital_clean)}")
        
        return self.combined_data
    def to_documents(self) -> list:
        """
        Convert cleaned BSC data into embedding-ready documents
        Returns list of dicts: {text, metadata}
        """
        if self.combined_data is None:
            self.merge_data()
        documents = []
        for _, row in self.combined_data.iterrows():
            text = f"""
            Strategic Objective: {row['strategic_objective']}
            KPI: {row['kpi']}
            Measurement: {row['measurement']}
            Target: {row['plan']}
            weight: {row['weight']}
            """
            metadata = {
                "source": "BSC",
                "division": row["division"],
                "kpi": row["kpi"]
            }
            documents.append({
                "text": text.strip(),
                "metadata": metadata
            })
        return documents