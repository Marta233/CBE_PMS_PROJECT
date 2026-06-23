"""
data_ingestion/api/main.py
FastAPI application entry point.

Run from the data_ingestion/ directory:
    uvicorn api.main:app --reload --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import ingest, index, status

app = FastAPI(
    title="Data Ingestion API",
    description="BSC · JD · LOS ingestion pipeline",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router, prefix="/api")
app.include_router(index.router,  prefix="/api")
app.include_router(status.router, prefix="/api")

@app.get("/", tags=["root"])
def root():
    return {"message": "Data Ingestion API running. See /docs"}
