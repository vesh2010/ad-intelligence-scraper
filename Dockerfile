FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    AD_SCRAPER_ENABLE_MONITOR_SCHEDULER=1 \
    AD_SCRAPER_MONITOR_POLL_SECONDS=60

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    python -m playwright install --with-deps chromium

COPY backend/app ./app
COPY data ./data

RUN mkdir -p /app/data/runs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
