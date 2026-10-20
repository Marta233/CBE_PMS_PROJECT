FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TOKENIZERS_PARALLELISM=false

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY Back_End /app/Back_End

WORKDIR /app/Back_End

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "scripts.API.main:app", "--host", "0.0.0.0", "--port", "8000"]
