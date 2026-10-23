FROM node:22-alpine AS frontend
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home commercepilot
COPY commercepilot/ ./commercepilot/
COPY app.py ./
COPY data/sample_products.json ./data/sample_products.json
COPY --from=frontend /build/frontend/dist ./frontend/dist
RUN mkdir -p /data && chown -R commercepilot:commercepilot /data /app/data
USER commercepilot
ENV DB_PATH=/data/commercepilot.sqlite3 SECRETS_DIR=/data/secrets PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
