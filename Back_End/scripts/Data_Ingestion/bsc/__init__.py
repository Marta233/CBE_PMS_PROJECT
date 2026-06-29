"""
bsc/__init__.py
---------------
Public entry-point for the BSC ingestion pipeline.

The ingest router calls:

    from bsc import run
    documents = run(file_path)

This module wires that call to BSCLoader so the router stays unaware of
the internal sheet names, column positions, or start-row conventions.
"""

from pathlib import Path
from typing import Union

from .bsc_loader import BSCLoader
from .config import (
    RBB_SHEET,
    DIGITAL_SHEET,
    COL_CONFIG,
    START_ROW,
)


def run(file_path: Union[str, Path]) -> list:
    """
    Load, clean, merge and convert a BSC Excel workbook to documents.

    Parameters
    ----------
    file_path : path to the uploaded BSC Excel file.

    Returns
    -------
    list of dicts  [{"text": str, "metadata": dict}, ...]
        Ready for JSON storage and FAISS embedding.
    """
    loader = BSCLoader(Path(file_path), config=COL_CONFIG)

    loader.load_separately(RBB_SHEET, DIGITAL_SHEET)
    loader.clean_rbb(start_row=START_ROW)
    loader.clean_digital(start_row=START_ROW)
    loader.merge_data()

    return loader.to_documents()