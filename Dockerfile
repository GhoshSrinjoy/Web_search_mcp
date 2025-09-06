FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application
COPY . .

# Create data directory
RUN mkdir -p /app/data/chroma_db

# Expose port for potential future web interface
EXPOSE 8000

# Default command
CMD ["python", "smart_ollama_chat.py"]