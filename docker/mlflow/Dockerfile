FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV MLFLOW_BACKEND_STORE_URI=sqlite:////mlflow/mlflow.db
ENV MLFLOW_ARTIFACTS_DESTINATION=/mlflow/artifacts
ENV MLFLOW_SERVER_ALLOWED_HOSTS=localhost:*,127.0.0.1:*,mlflow:5000
ENV MLFLOW_SERVER_CORS_ALLOWED_ORIGINS=http://localhost:5000,http://127.0.0.1:5000

WORKDIR /mlflow

COPY requirements-mlflow.txt ./
RUN pip install --no-cache-dir -r requirements-mlflow.txt

RUN adduser --disabled-password --gecos "" appuser && chown -R appuser:appuser /mlflow
USER appuser

EXPOSE 5000

CMD ["sh", "-c", "exec mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri \"$MLFLOW_BACKEND_STORE_URI\" --serve-artifacts --artifacts-destination \"$MLFLOW_ARTIFACTS_DESTINATION\" --allowed-hosts \"$MLFLOW_SERVER_ALLOWED_HOSTS\" --cors-allowed-origins \"$MLFLOW_SERVER_CORS_ALLOWED_ORIGINS\""]
