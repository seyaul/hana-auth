# --- Dockerfile (root of your auth project) -----------------------
FROM python:3.12-slim

# Install system libs your wheels may need
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential && \
    rm -rf /var/lib/apt/lists/*

# Copy dependency list & install
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Expose port Fly defaults to (8080)
EXPOSE 8080

# Start FastAPI with uvicorn
CMD ["uvicorn", "app:app", "--host=0.0.0.0", "--port=8080"]
