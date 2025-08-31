FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including build tools for lxml
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    g++ \
    libxml2-dev \
    libxslt-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8055}/health || exit 1

# Expose port
EXPOSE 8055

# Run the application
CMD ["python", "app.py"]