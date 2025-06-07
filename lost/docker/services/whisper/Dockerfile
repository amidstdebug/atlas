# Use a specific and stable PyTorch base image
FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime

# Set the working directory
WORKDIR /usr/src/app

# Set environment variables to prevent interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies required for audio processing
# This installs the C-library for handling audio files
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the application code into the container
# Copying the 'app' directory is more efficient than copying the whole context
COPY . /usr/src/app

# Expose the port the app will run on
EXPOSE 8000

# Command to run the application using uvicorn
# The path must be 'app.main:app' because our code is inside the 'app' directory
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
