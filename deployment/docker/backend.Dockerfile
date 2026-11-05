FROM node:22-bookworm-slim AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM python:3.13-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-deu tesseract-ocr-ara libmagic1 fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 1001 omnifix
WORKDIR /app
COPY backend/requirements.lock /app/backend/requirements.lock
RUN pip install --no-cache-dir -r /app/backend/requirements.lock
COPY backend /app/backend
COPY processing /app/processing
COPY --from=frontend-build /build/out /app/frontend/out
RUN mkdir -p /app/storage && chown -R omnifix:omnifix /app
USER omnifix
WORKDIR /app/backend
ENV DATA_DIR=/app/storage FRONTEND_DIR=/app/frontend/out HOST=0.0.0.0 PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
