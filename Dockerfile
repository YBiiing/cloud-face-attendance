FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/app
RUN apt-get update && apt-get install -y --no-install-recommends g++ && rm -rf /var/lib/apt/lists/*
COPY requirements.in requirements.lock .
RUN pip install --no-cache-dir numpy==1.26.4 cython==3.3.0 setuptools==79.0.1 wheel==0.46.3 && pip install --no-cache-dir --no-build-isolation -r requirements.lock
COPY requirements-jobs.in requirements-jobs.lock .
RUN pip install --no-cache-dir -r requirements-jobs.lock
COPY app ./app
COPY web ./web
COPY migrations ./migrations
COPY alembic.ini .
COPY scripts ./scripts
RUN useradd --create-home appuser && mkdir -p /srv/storage /srv/models && chown -R appuser:appuser /srv/storage /srv/models
USER appuser
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

FROM runtime AS testing
USER root
COPY requirements-dev.in .
RUN pip install --no-cache-dir -r requirements-dev.in
COPY tests ./tests
COPY pytest.ini .
USER appuser
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]
