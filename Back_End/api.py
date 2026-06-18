# Back_End/api.py
# Run from the Back_End folder:
#   uvicorn api:app --host 0.0.0.0 --port 8000 --reload
#
# Or from the project root:
#   uvicorn Back_End.api:app --host 0.0.0.0 --port 8000 --reload
#
# All logic stays in Back_End/scripts/API.py

from scripts.API import app  # noqa: F401
