FROM python:3.11-slim

WORKDIR /app

# Install minimal system dependencies
# build-essential covers gcc + compilation tools for Python packages with C extensions
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY trading_websocket/ ./trading_websocket/
COPY producer.py .
COPY producer_ws.py .

# Default: REST polling producer (reliable, optimized with 5s POLL_INTERVAL)
CMD ["python", "-u", "producer.py"]
