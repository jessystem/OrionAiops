FROM python:3.12-slim

WORKDIR /app

# libgomp é requisito do LightGBM
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY run_pipeline.py .

ENV PYTHONPATH=/app/src
EXPOSE 8000

# Sobe a API. Para rodar o pipeline:
#   docker run orion-aiops python run_pipeline.py
CMD ["uvicorn", "orion.api:app", "--host", "0.0.0.0", "--port", "8000"]
