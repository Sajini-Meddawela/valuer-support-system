FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SOFFICE_PATH=/usr/bin/libreoffice

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libreoffice-core \
        libreoffice-writer \
        fonts-dejavu-core \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/* \
    && command -v libreoffice

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt

RUN python -m pip install --upgrade pip \
    && python -m pip install -r /app/backend/requirements.txt

COPY backend /app/backend

WORKDIR /app/backend

RUN mkdir -p /app/backend/data

CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
