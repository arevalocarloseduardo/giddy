FROM pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/root/.cache/huggingface \
    HF_HUB_DISABLE_XET=1 \
    HF_HUB_DOWNLOAD_TIMEOUT=180 \
    HF_HUB_ETAG_TIMEOUT=30

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY generate.py /app/generate.py

ENTRYPOINT ["python", "/app/generate.py"]
