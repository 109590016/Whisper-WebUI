FROM nvidia/cuda:12.3.2-cudnn9-runtime-ubuntu22.04

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        ffmpeg \
        python3 \
        python3-pip \
        python3-venv && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /Whisper-WebUI

COPY requirements.txt .
RUN python3 -m venv /opt/recordtrans && \
    /opt/recordtrans/bin/pip install --no-cache-dir --upgrade pip==24.3.1 && \
    /opt/recordtrans/bin/pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PATH="/opt/recordtrans/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    RECORDTRANS_MODEL_DIR=/Whisper-WebUI/models \
    RECORDTRANS_MODEL=small \
    RECORDTRANS_DEVICE=cuda \
    RECORDTRANS_COMPUTE_TYPE=float16

VOLUME ["/data", "/Whisper-WebUI/models"]
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=5 \
    CMD curl --fail http://127.0.0.1:7860/ || exit 1

ENTRYPOINT ["python", "app.py"]
CMD ["--server_name", "0.0.0.0", "--server_port", "7860"]
