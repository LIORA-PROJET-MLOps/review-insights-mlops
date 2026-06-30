FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV DAGSTER_HOME=/opt/dagster/dagster_home
ENV GIT_PYTHON_REFRESH=quiet

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
    && mkdir -p \
        /opt/dagster/dagster_home \
        /opt/dagster/storage/artifacts \
        /opt/dagster/storage/compute_logs \
        /app/data_store/raw/incoming \
        /app/data_store/raw/archive \
        /app/data_store/processed \
        /app/data_store/validated \
        /app/data_store/quarantine \
        /app/data_store/splits \
        /app/data_store/registry \
        /app/data_store/sample \
        /app/predictions \
        /app/feedback \
        /app/artifacts \
        /app/reports \
    && cp /app/orchestration/dagster.yaml /opt/dagster/dagster_home/dagster.yaml \
    && chown -R appuser:appuser /app /opt/dagster

USER appuser

EXPOSE 3000 4000
