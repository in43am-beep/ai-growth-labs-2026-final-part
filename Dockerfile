# ===== Stage 1: build Python dependencies =====
FROM python:3.12-slim AS deps
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*
COPY dashboard/requirements.txt /app/dashboard/requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r /app/dashboard/requirements.txt

# ===== Stage 2: runtime (FastAPI + nginx) =====
FROM python:3.12-slim AS runtime
WORKDIR /app

# nginx for static serving + reverse proxy
RUN apt-get update && apt-get install -y --no-install-recommends nginx curl \
    && rm -rf /var/lib/apt/lists/*

# Bring in installed python packages from the deps stage
COPY --from=deps /install /usr/local

# Copy application code + static frontend
COPY . /app

# nginx config
COPY nginx.conf /etc/nginx/nginx.conf
COPY proxy_headers.conf /etc/nginx/proxy_headers.conf

ENV FRONTEND_DIR=/app
ENV PYTHONUNBUFFERED=1

# nginx serves public traffic on 8080; FastAPI runs internally on 8000
EXPOSE 8080 8000

# Health check hits FastAPI directly (port-stable across platforms)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh
CMD ["/app/start.sh"]
