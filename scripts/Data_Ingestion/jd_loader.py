# jd_loader.py
"""Complete JD Loader - Single script similar to BSC loader"""

import pandas as pd
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from docx import Document
import sys

# Add parent directory to path if needed
sys.path.insert(0, str(Path(__file__).parent))

from config import JD_FILE_PATH, OUTPUT_PATH, JD_FIELDS


class JDLoader:
    """Load and process Job Description data - Similar to BSCLoader"""
    
    def __init__(self, file_path: Optional[Path] = None):
        """
        Initialize JD Loader.
        
        Args:
            file_path: Path to Word document. If None, uses default path.
        """
        self.file_path = file_path or JD_FILE_PATH
        self.raw_data = None
        self.processed_data = None
        print(f"📁 JDLoader initialized with: {self.file_path}")
    
    def load_document(self) -> pd.DataFrame:
        """
        Load and extract all job descriptions from Word document.
        
        Returns:
            DataFrame with raw JD data
        """
        try:
            print(f"\n📂 Loading JD file: {self.file_path.name}")
            doc = Document(self.file_path)
            jd_records = []
            for table_idx, table in enumerate(doc.tables):
                # Extract table text
                table_text = ""
                for row in table.rows:
                    row_text = " | ".join([cell.text.strip() for cell in row.cells if cell.text.strip()])
                    table_text += row_text + "\n"
                # Normalize text
                table_text = table_text.lower()
                table_text = re.sub(r'\s+', ' ', table_text)
                # Extract fields
                def extract_field(field_name):
                    pattern = rf"{field_name}\s*:\s*([^|]+)"
                    match = re.search(pattern, table_text)
                    return match.group(1).strip() if match else None
                
                # Extract job title (special handling)
                job_title = self._extract_job_title(table)
                if not job_title:
                    job_title = extract_field("job title")
                # Extract responsibilities
                responsibilities = self._extract_responsibilities(table_text)
                record = {
                    "job_title": job_title,
                    "division": extract_field("division"),
                    "department": extract_field("department"),
                    "job_grade": extract_field("job grade"),
                    "job_category": extract_field("job category"),
                    "job_objective": extract_field("job objective"),
                    "responsibilities": responsibilities,
                    "full_text": table_text
                }
                # Only add if we have a job title
                if record["job_title"]:
                    jd_records.append(record)
                    print(f"  ✓ Extracted: {record['job_title']} ({len(responsibilities)} responsibilities)")
            
            self.raw_data = pd.DataFrame(jd_records)
            print(f"\n✅ Total job descriptions extracted: {len(self.raw_data)}")
            return self.raw_data
        except FileNotFoundError:
            print(f"❌ JD file not found at {self.file_path}")
            raise
        except Exception as e:
            print(f"❌ Error loading JD data: {e}")
            raise
    def _extract_job_title(self, table) -> Optional[str]:
        """Extract job title from Word table."""
        for row in table.rows:
            for cell in row.cells:
                text = cell.text.strip()
                if 'job title:' in text.lower():
                    return text.split(':', 1)[1].strip()
                elif len(text) > 10 and not any(x in text.lower() for x in ['job', 'code', 'division', 'department', 'grade']):
                    if not any(x in text.lower() for x in ['table', 'figure', 'page']):
                        return text
        return None
    def _extract_responsibilities(self, table) -> List[str]:
        """Extract responsibilities directly from Word table structure."""
        responsibilities = []
        capture = False
        for row in table.rows:
            for cell in row.cells:
                text = cell.text.strip()
                if not text:
                    continue
                lower_text = text.lower()
                # start section
                if "key job duties and responsibilities" in lower_text:
                    capture = True
                    continue

                # stop conditions
                if capture and any(x in lower_text for x in [
                    "key performance indicators",
                    "qualifications",
                    "education",
                    "experience"
                ]):
                    capture = False

                # collect bullets
                if capture:
                    cleaned = text.strip()

                    # remove header-like noise
                    cleaned = re.sub(r"^[•\-]\s*", "", cleaned)

                    if len(cleaned) > 5:
                        responsibilities.append(cleaned)

        return responsibilities
    def clean_data(self) -> pd.DataFrame:
        """
        Clean and validate JD data.
        
        Returns:
            Cleaned DataFrame
        """
        if self.raw_data is None:
            self.load_document()
        
        print("\n📋 Cleaning JD data...")
        
        # Make a copy
        self.processed_data = self.raw_data.copy()
        
        # Remove rows with no job title
        self.processed_data = self.processed_data.dropna(subset=['job_title'])
        self.processed_data = self.processed_data[self.processed_data['job_title'].astype(str).str.lower() != 'none']
        
        # Clean text fields
        text_fields = ['job_title', 'division', 'department', 'job_grade', 'job_category', 'job_objective']
        for field in text_fields:
            if field in self.processed_data.columns:
                self.processed_data[field] = self.processed_data[field].astype(str).str.strip()
                self.processed_data[field] = self.processed_data[field].replace('nan', '')
                self.processed_data[field] = self.processed_data[field].replace('None', '')
        
        # Add responsibility count
        self.processed_data['num_responsibilities'] = self.processed_data['responsibilities'].apply(len)
        
        # Extract numeric job grade
        def extract_grade(grade_str):
            if isinstance(grade_str, str):
                match = re.search(r'(\d+)', grade_str)
                if match:
                    return int(match.group(1))
            return None
        
        self.processed_data['job_grade'] = self.processed_data['job_grade'].apply(extract_grade)
        
        print(f"  ✅ Cleaned {len(self.processed_data)} job descriptions")
        print(f"  📊 Total responsibilities: {self.processed_data['num_responsibilities'].sum()}")
        
        return self.processed_data
    
    def get_data(self) -> pd.DataFrame:
        """Get processed data."""
        if self.processed_data is None:
            self.clean_data()
        return self.processed_data
    
    def get_job_titles(self) -> List[str]:
        """Get list of all job titles."""
        if self.processed_data is None:
            self.clean_data()
        return self.processed_data['job_title'].tolist()
    
    def get_job_by_title(self, title: str) -> Optional[Dict]:
        """Get specific job by title."""
        if self.processed_data is None:
            self.clean_data()
        
        match = self.processed_data[self.processed_data['job_title'].str.contains(title, case=False, na=False)]
        if not match.empty:
            return match.iloc[0].to_dict()
        return None
    
    def save_to_csv(self, output_path: Optional[Path] = None) -> str:
        """
        Save raw data to CSV.
        
        Args:
            output_path: Path where to save CSV file
            
        Returns:
            Path to saved file
        """
        if self.processed_data is None:
            self.clean_data()
        
        output_path = output_path or OUTPUT_PATH
        csv_path = output_path / "jd_processed_data.csv"
        self.processed_data.to_csv(csv_path, index=False)
        print(f"✅ Saved to: {csv_path}")
        return str(csv_path)
    
    def save_responsibilities_expanded(self, output_path: Optional[Path] = None) -> str:
        """
        Save expanded responsibilities to CSV (one responsibility per row).
        
        Args:
            output_path: Path where to save CSV file
            
        Returns:
            Path to saved file
        """
        if self.processed_data is None:
            self.clean_data()
        
        output_path = output_path or OUTPUT_PATH
        
        expanded_rows = []
        for idx, row in self.processed_data.iterrows():
            responsibilities = row.get('responsibilities', [])
            for resp_idx, resp in enumerate(responsibilities):
                expanded_rows.append({
                    'job_title': row.get('job_title'),
                    'division': row.get('division'),
                    'department': row.get('department'),
                    'job_grade': row.get('job_grade'),
                    'job_category': row.get('job_category'),
                    'job_objective': row.get('job_objective'),
                    'responsibility_index': resp_idx + 1,
                    'responsibility': resp
                })
        
        expanded_df = pd.DataFrame(expanded_rows)
        csv_path = output_path / "jd_responsibilities_expanded.csv"
        expanded_df.to_csv(csv_path, index=False)
        print(f"✅ Saved expanded responsibilities to: {csv_path}")
        return str(csv_path)
    
    def get_summary(self) -> Dict:
        """Get summary statistics (optional - if you want)."""
        if self.processed_data is None:
            self.clean_data()
        
        return {
            'total_jobs': len(self.processed_data),
            'unique_divisions': self.processed_data['division'].nunique(),
            'unique_departments': self.processed_data['department'].nunique(),
            'avg_responsibilities': self.processed_data['num_responsibilities'].mean(),
            'total_responsibilities': self.processed_data['num_responsibilities'].sum()
        }


