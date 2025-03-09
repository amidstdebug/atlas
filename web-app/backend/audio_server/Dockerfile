# Use the official PyTorch image as the base image
FROM nvcr.io/nvidia/nemo:24.07

# Set the working directory
WORKDIR /usr/src/app

# Install system dependencies
RUN apt-get -y update
RUN apt-get install -y libsndfile1

# Copy the requirements file
COPY requirements.txt .

# Install pip dependencies from requirements.txt
RUN pip uninstall transformer-engine -y
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install -U soundfile
RUN pip install -U torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
RUN pip install https://github.com/Dao-AILab/flash-attention/releases/download/v2.5.8/flash_attn-2.5.8+cu118torch2.3cxx11abiFALSE-cp310-cp310-linux_x86_64.whl

# Install HuggingFace Transformers with optional dependencies for Whisper
# RUN pip install -U transformers[torch]

# Copy the audio_server directory
COPY ./ /usr/src/app/

# Create models directory
RUN mkdir -p /usr/src/app/models

# Expose port for FastAPI
EXPOSE 8000

# Command to run FastAPI server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]