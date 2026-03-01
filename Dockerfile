# Dockerfile for configuration

# Base image
# FROM python:3.11-slim

# Set working directory
# WORKDIR /app

# Copy requirement files and install
# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt

# Copy the app source code
# COPY . .

# NOTE: Ensure the .env file is copied into the container or mounted at runtime
# Example: COPY .env .env

# Expose port and define entrypoint
# EXPOSE 8000
# CMD ["fastapi", "run"]
