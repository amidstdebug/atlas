# Use the official PyTorch image as the base image
FROM pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime

# Set the working directory
WORKDIR /usr/src/app

# Install system dependencies for sndfile (libsndfile1-dev)
# RUN apt-get update && apt-get install -y libsndfile1-dev
RUN apt-get -y update
RUN apt-get install -y libsndfile1
# RUN apt-get install -y sox
# Copy the requirements.txt file to the container
COPY requirements.txt .

# Install pip dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code to the container
# COPY . .

# Expose port 5000
EXPOSE 5000

# Set environment variables for Flask
ENV FLASK_APP=app.py
ENV FLASK_ENV=development

# Command to run the Flask app
CMD ["flask", "run", "--host=0.0.0.0"]
