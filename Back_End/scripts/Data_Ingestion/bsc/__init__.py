"""
bsc/__init__.py
---------------
Public entry-point for the BSC ingestion pipeline.

The ingest router calls:

    from bsc import run
    documents = run(file_path)

One loader serves every division: each sheet of the workbook is a division, named through the
organisation registry (common/org_registry.json).
"""

from pathlib import Path
from typing import Union

from .bsc_loader import BSCLoader
from .config import COL_CONFIG, START_ROW


def run(file_path: Union[str, Path]) -> list:
    """
    Load, clean, merge and convert a BSC Excel workbook to documents.

    Returns a list of dicts  [{"text": str, "metadata": dict}, ...]
    """
    loader = BSCLoader(Path(file_path), config=COL_CONFIG)
    loader.load_all_sheets()
    loader.clean_all_sheets(start_row=START_ROW)
    loader.merge_data()
    return loader.to_documents()
