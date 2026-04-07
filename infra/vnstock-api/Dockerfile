FROM python:3.11-slim AS base

# Tránh tạo .pyc file → tiết kiệm disk trong container
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Layer cache: chỉ rebuild khi requirements thay đổi
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/

# Non-root user cho security
RUN adduser --disabled-password --no-create-home appuser
USER appuser

EXPOSE 8000

# Uvicorn: 2 workers, giới hạn backlog để kiểm soát RAM trên 32GB host
# --limit-max-requests=10000 để tránh memory leak dài hạn
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--limit-max-requests", "10000", \
     "--timeout-keep-alive", "30", \
     "--access-log"]
