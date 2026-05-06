FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements-api.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements-api.txt

COPY api_app.py ./
COPY src ./src
COPY models ./models

RUN adduser --disabled-password --gecos "" appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "api_app:app", "--host", "0.0.0.0", "--port", "8000"]
