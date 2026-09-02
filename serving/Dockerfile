# Inference image for the IDS service. Kept deliberately small and explicit:
# the paper reports image size and cold-start time, so both must be
# reproducible from this file alone.
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=1 \
    ARTIFACT_DIR=/app/artifacts

WORKDIR /app

RUN pip install --no-cache-dir \
      fastapi==0.115.5 \
      "uvicorn[standard]==0.32.0" \
      numpy==2.2.3 \
      scikit-learn==1.5.2 \
      xgboost==3.4.1 \
      joblib==1.5.3

COPY app.py /app/app.py
COPY artifacts /app/artifacts

# A non-root user: the deployment sets runAsNonRoot, and the image must match.
RUN useradd -r -u 10001 ids && chown -R ids:ids /app
USER ids

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status==200 else 1)"

# One worker per pod: scaling is the cluster's job, not the process manager's,
# so that the HPA measurement is not confounded by in-pod parallelism.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
