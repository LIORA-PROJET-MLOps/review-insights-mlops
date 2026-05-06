FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /mlflow

COPY requirements-mlflow.txt ./
RUN pip install --no-cache-dir -r requirements-mlflow.txt

RUN adduser --disabled-password --gecos "" appuser && chown -R appuser:appuser /mlflow
USER appuser

EXPOSE 5000

CMD ["mlflow", "server", "--host", "0.0.0.0", "--port", "5000", "--backend-store-uri", "sqlite:////mlflow/mlflow.db", "--default-artifact-root", "/mlflow/artifacts"]
