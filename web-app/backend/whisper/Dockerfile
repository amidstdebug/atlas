# Use the official PyTorch image as the base image
FROM pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime

# Set the working directory
WORKDIR /usr/src/app

# Copy the conda environment archive created by conda-pack
COPY env.tar.gz .

# Unpack the environment and remove the archive
RUN mkdir -p /opt/conda/envs/myenv && \
    tar -xzf env.tar.gz -C /opt/conda/envs/myenv && \
    rm env.tar.gz

# Set the path to the conda environment
ENV PATH /opt/conda/envs/myenv/bin:$PATH

# Copy the rest of the application code
COPY . .

# Expose port 5000
EXPOSE 5000

# Set the environment variables for Flask
ENV FLASK_APP=app.py
ENV FLASK_ENV=development

# Command to run the Flask app
CMD ["flask", "run", "--host=0.0.0.0"]
