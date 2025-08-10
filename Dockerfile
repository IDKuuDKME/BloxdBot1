# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies including the browser AND the driver
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application's code into the container
COPY . .

# Ensure logs are sent straight to Render's log stream
ENV PYTHONUNBUFFERED=1

# [CORRECT COMMAND] Use gunicorn to run the flask_app object inside the app.py file.
# This starts the web server so your Render URL will work.
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "--workers", "1", "app:flask_app"]
