FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    g++ \
    libreoffice \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt huggingface_hub

# Configure MinerU (magic-pdf)
RUN mkdir -p /root/.mineru/models && \
    echo '{ \
      "models-dir": "/root/.mineru/models", \
      "device-mode": "cpu", \
      "table-config": { "model": "rapid_table", "enable": false, "max_time": 400 }, \
      "layout-config": { "model": "doclayout_yolo" }, \
      "formula-config": { "mfd_model": "yolov8_mfd", "mfr_model": "unimernet_v2_small", "enable": false } \
    }' > /root/magic-pdf.json

# Download MinerU AI Models (~5GB)
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='opendatalab/pdf-extract-kit-1.0', local_dir='/root/.mineru/models')"

COPY . .

ENV PYTHONPATH=/app

CMD ["python", "main.py"]
