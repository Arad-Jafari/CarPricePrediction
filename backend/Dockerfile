FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/backend

WORKDIR /app/backend

RUN apt-get update \
    && apt-get install --no-install-recommends -y libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app app

COPY backend/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r /tmp/requirements.txt

COPY --chown=app:app backend/ /app/backend/
COPY --chown=app:app ml/__init__.py /app/ml/__init__.py
COPY --chown=app:app ml/inference.py /app/ml/inference.py
COPY --chown=app:app ml/feature_contract.json /app/ml/feature_contract.json
COPY --chown=app:app ml/artifacts/CarPredictionModel.pkl /app/ml/artifacts/CarPredictionModel.pkl
COPY --chown=app:app ml/artifacts/CarPreprocessor.pkl /app/ml/artifacts/CarPreprocessor.pkl

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
