# Use Python 3.12 slim image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies directly
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir \
    fastmcp>=2.11.0 \
    google-auth>=2.28.1 \
    google-auth-oauthlib>=1.2.0 \
    google-api-python-client>=2.117.0 \
    pydantic>=2.11.7 \
    python-dotenv>=1.1.0 \
    uvicorn>=0.35.0

# Copy source code
COPY src/ ./src/

# Copy service account key for authentication
COPY service-account-key.json ./service-account-key.json

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Set Python path and run the application
ENV PYTHONPATH=/app/src
CMD ["python", "-m", "google_sheets_mcp_server"]
