"""
Run from Back_End/:
    uvicorn app:api --reload
"""
from scripts.API.main import app as api

__all__ = ["api"]
