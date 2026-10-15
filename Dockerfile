# Courtfield: one container serving the API and the built web app.

# ---- build the web app ----
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- run the API ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    COURTFIELD_ENV=production FRONTEND_DIST=/app/web
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=web /web/dist /app/web
RUN useradd --system --uid 10001 courtfield && chmod +x start.sh
USER courtfield
EXPOSE 8000
CMD ["./start.sh"]
