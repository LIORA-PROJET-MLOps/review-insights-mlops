FROM python:3.12-slim

WORKDIR /app

COPY . /app

EXPOSE 7860

CMD ["python", "-m", "http.server", "7860", "--directory", "/app"]
