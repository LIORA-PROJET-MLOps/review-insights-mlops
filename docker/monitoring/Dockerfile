FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements-monitoring.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements-monitoring.txt

COPY monitoring_app.py ./
COPY src ./src

RUN adduser --disabled-password --gecos "" appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 9000

CMD ["uvicorn", "monitoring_app:app", "--host", "0.0.0.0", "--port", "9000"]
