FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CHROMA_PATH=/data/chroma \
    UPLOAD_DIR=/data/uploads

WORKDIR /app

# Dependencies first, so editing code does not reinstall every package
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

# Run as a normal user, not root. /data is where documents are kept.
RUN useradd --create-home --uid 10001 verity \
    && mkdir -p /data \
    && chown verity:verity /data
USER verity

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
