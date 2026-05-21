# ═════════════════════════════════════════════════════════════════════════════
# ENDPOINT 2 — DATA INGESTION  (admin only, call when source data changes)
# ═════════════════════════════════════════════════════════════════════════════

@app.post("/api/ingest")
def ingest():
    """
    ADMIN ONLY — call this when BSC, JD, or LOS source data has changed.

    Re-runs the data ingestion pipelines and rebuilds the BSC FAISS index.
    After this completes, /api/generate will use the updated data.

    The React UI should put this behind an admin screen, not the main user flow.
    """
    global extractor

    try:
        # re-import config to re-run ingestion pipelines
        import importlib
        import config as cfg
        importlib.reload(cfg)

        # rebuild BSC FAISS index
        bsc_lc = [
            Document(page_content=d["text"], metadata=d.get("metadata", {}))
            if isinstance(d, dict) else d
            for d in cfg.BSC_DOCUMENTS
        ]
        new_bsc_vs = PMSVectorStore(
            embedding_model=cfg.EMBEDDING_MODEL,
            index_path=BSC_FAISS_PATH,
        )
        new_bsc_vs.create_vectorstore(bsc_lc)
        new_bsc_vs.save_vectorstore()

        # rebuild extractor with fresh data
        extractor = QueryExtractor(
            los_docs=list(cfg.LOS_DOCUMENTS),
            jd_docs=list(cfg.JD_DOCUMENTS),
            bsc_vectorstore=new_bsc_vs,
        )

        return {
            "message": "Ingestion complete. FAISS index rebuilt.",
            "bsc_docs": len(bsc_lc),
            "los_docs": len(cfg.LOS_DOCUMENTS),
            "jd_docs":  len(cfg.JD_DOCUMENTS),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")