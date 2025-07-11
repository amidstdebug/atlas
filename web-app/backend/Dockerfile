FROM python:3.10-slim

WORKDIR /usr/src/app

# Install dependencies
COPY requirements.txt .
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create a non-root user
RUN adduser --disabled-password --gecos '' appuser
RUN chown -R appuser:appuser /usr/src/app
USER appuser

# Expose the port the app runs on
EXPOSE 5002

# Command to run the application
CMD ["python", "main.py"]