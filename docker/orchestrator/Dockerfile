FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV DAGSTER_HOME=/opt/dagster/dagster_home

WORKDIR /app

COPY requirements-orchestrator.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements-orchestrator.txt

COPY pipelines ./pipelines
COPY src ./src
COPY orchestration ./orchestration
COPY config ./config
COPY data/contracts ./data/contracts
COPY data/sample ./data/sample
COPY models ./models

RUN adduser --disabled-password --gecos "" appuser \
    && mkdir -p /opt/dagster/dagster_home /opt/dagster/storage/artifacts /opt/dagster/storage/compute_logs /app/data_store /app/artifacts /app/reports \
    && cp /app/orchestration/dagster.yaml /opt/dagster/dagster_home/dagster.yaml \
    && chown -R appuser:appuser /app /opt/dagster

USER appuser

EXPOSE 3000 4000
