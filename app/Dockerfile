# llm-guard 0.3.x supports Python 3.10 to 3.12 only.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/opt/hf \
    NLTK_DATA=/opt/nltk

WORKDIR /app

# CPU-only torch keeps the image far smaller than the default CUDA build.
RUN pip install --index-url https://download.pytorch.org/whl/cpu "torch==2.5.1"

COPY requirements.txt .
RUN pip install -r requirements.txt \
    && python -m spacy download en_core_web_sm \
    && python -m nltk.downloader -d /opt/nltk punkt punkt_tab

COPY gateway ./gateway
COPY scripts ./scripts

# Bake all model weights into the image, then forbid runtime downloads.
RUN PYTHONPATH=/app python scripts/warm_models.py

ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    HOME=/tmp \
    TMPDIR=/tmp

# Run as an unprivileged user; the ECS task also mounts a read-only root filesystem.
RUN useradd --system --uid 10001 --no-create-home gateway \
    && chmod -R a+rX /opt /app
USER 10001

EXPOSE 8080
CMD ["uvicorn", "gateway.main:app_factory", "--factory", "--host", "0.0.0.0", "--port", "8080", "--no-server-header"]
