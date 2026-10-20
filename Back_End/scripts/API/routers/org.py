"""Organisation tree for dropdowns. Names come from org_registry.json."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/org", tags=["org"])
def org_tree():
    try:
        from common import registry
    except ImportError:
        from Data_Ingestion.common import registry
    return {"divisions": registry.list_tree()}
