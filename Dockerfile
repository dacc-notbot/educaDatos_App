FROM python:3.11.16-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2

WORKDIR /app

COPY requirements.lock .

RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir --require-hashes -r requirements.lock \
    && adduser --disabled-password --gecos "" app

COPY --chown=app:app . .

USER app

CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
