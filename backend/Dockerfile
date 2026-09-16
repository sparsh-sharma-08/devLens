FROM python:3.12-slim

WORKDIR /app

# System dependencies for Tree-sitter, Git, static analysis tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    gcc \
    g++ \
    build-essential \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install ESLint globally for JS/TS static analysis
RUN npm install -g eslint

# Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e ".[dev]"

# Copy application code
COPY . .

EXPOSE 8000
