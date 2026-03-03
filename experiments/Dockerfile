# Use an official lightweight Python image.
FROM python:3.11-slim

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED True

# Set the working directory
WORKDIR /experiments

# Copy requirements
COPY requirements-experiments.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements-experiments.txt

# Create a non-root user and switch to it
RUN useradd -m appuser \
    && chown -R appuser:appuser /experiments

USER appuser

# Expose Jupyter port
EXPOSE 8888

# Command to run Jupyter Notebook (without security token for local ease of use, you can update this later)
CMD ["jupyter", "notebook", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--NotebookApp.token=''", "--NotebookApp.password=''"]
