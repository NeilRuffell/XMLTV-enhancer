FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

ENV PORT=8765
EXPOSE 8765

CMD ["sh", "-c", "uvicorn xmltv_enricher.app:app --host 0.0.0.0 --port ${PORT:-8765}"]
