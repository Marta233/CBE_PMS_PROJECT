# Back_End/api.py
# Run from the Back_End folder:
#
#   python run_app.py              ← API + Celery worker (recommended)
#   python run_app.py --no-worker  ← API only
#
# Or API alone:
#   uvicorn api:app --host 0.0.0.0 --port 8000 --reload
#
# All logic stays in Back_End/scripts/API.py

from scripts.API import app  # noqa: F401
