# ReportSDState API image. Built by deploy/docker-compose.yml.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY wsgi.py serve.py docker-entrypoint.sh ./
RUN chmod 755 docker-entrypoint.sh && mkdir -p instance

# The compose file runs the container as the host user that owns the data folder.
# This default only applies when the image is run on its own.
USER 10001:10001

EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/v1/health', timeout=4)"

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["python", "serve.py"]
