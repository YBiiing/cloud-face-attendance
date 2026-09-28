FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/app
COPY requirements.in .
RUN pip install --no-cache-dir -r requirements.in
COPY app ./app
COPY web ./web
RUN useradd --create-home appuser && mkdir -p /srv/storage /srv/models && chown -R appuser:appuser /srv/storage /srv/models
USER appuser
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
