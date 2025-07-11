FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends git ffmpeg python3-pip && \
    rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/ufal/SimulStreaming.git /app/SimulStreaming
WORKDIR /app/SimulStreaming
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

RUN mkdir -p /models

EXPOSE 43007

CMD ["python", "simulstreaming_whisper_server.py", "--host", "0.0.0.0", "--port", "43007", "--model_path", "/models/large-v3.pt"]
