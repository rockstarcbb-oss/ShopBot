FROM python:3.12-slim

WORKDIR /bot
COPY . .
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt
ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "alembic upgrade head && python -u run.py"]