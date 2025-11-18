# Multi-stage build pour optimiser la taille de l'image
FROM python:3.10-slim AS builder

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    unixodbc-dev \
    libpq-dev \
    curl \
    gnupg2 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements-simple.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV ACCEPT_EULA=Y

# ===== INSTALLATION DES DRIVERS SQL SERVER =====
# Installation des dépendances système et des drivers Microsoft ODBC
RUN apt-get update && apt-get install -y \
    curl \
    gnupg2 \
    apt-transport-https \
    ca-certificates \
    libpq5 \
    unixodbc \
    unixodbc-dev \
    && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && apt-get install -y mssql-tools18 \
    && echo 'export PATH="$PATH:/opt/mssql-tools18/bin"' >> /etc/bash.bashrc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Créer le répertoire pour les certificats SSL
RUN mkdir -p /etc/ssl/certs

# Create non-root user for security
RUN useradd -m -u 1000 appuser

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder stage and fix permissions
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# Set PATH to use appuser's local bin
ENV PATH=/home/appuser/.local/bin:/opt/mssql-tools18/bin:$PATH

# Copy application code
COPY --chown=appuser:appuser . .

# Create directories for logs and uploaded files
RUN mkdir -p /app/logs /app/uploaded_files && \
    chown -R appuser:appuser /app

# Vérifier que le fichier Firebase existe (optionnel - pour debug)
RUN test -f /app/app/samaconso-firebase-adminsdk-fbsvc-ae9b8fc3c0.json || echo "⚠️ WARNING: Firebase credentials not found"

USER appuser

# Expose port 8000
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Default command (can be overridden in docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
