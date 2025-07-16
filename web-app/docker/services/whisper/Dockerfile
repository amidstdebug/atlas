FROM nvidia/cuda:12.6.0-cudnn-devel-ubuntu22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    ffmpeg \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create symlinks for python commands
RUN ln -sf /usr/bin/python3 /usr/bin/python
RUN ln -sf /usr/bin/pip3 /usr/bin/pip

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cu121

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]