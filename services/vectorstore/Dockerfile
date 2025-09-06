FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory for ChromaDB
RUN mkdir -p /app/data/chroma_db

# Expose port if needed (currently not used as a standalone service)
EXPOSE 8000

# Default command - this service is typically used as a library
CMD ["python", "-c", "from content_vectorizer import ContentVectorizer; print('Vectorstore service ready')"]