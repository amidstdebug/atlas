# Dockerfile
FROM nvcr.io/nvidia/nemo:24.07

# Set the working directory
WORKDIR /usr/src/app

# Install additional OS dependencies
RUN apt-get update && apt-get install -y wget sox libsndfile1 ffmpeg

# Copy the requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the rest of the code
COPY . .

# Expose port 5002 (or any port you choose)
EXPOSE 5002

# Run the FastAPI server using Uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5002"]