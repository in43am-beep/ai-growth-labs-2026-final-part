FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY dashboard/requirements.txt /app/dashboard/requirements.txt
RUN pip install --no-cache-dir -r /app/dashboard/requirements.txt

# Copy all project files
COPY . /app

# Expose port
EXPOSE 8080

# Start script
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
