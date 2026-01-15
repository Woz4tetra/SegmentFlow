# Backend Dockerfile with SAM3 support
# Use NVIDIA CUDA-capable PyTorch image with Python 3.12 and pre-installed deep learning dependencies
FROM nvidia/cuda:13.0.0-devel-ubuntu24.04

WORKDIR /app

# Install system dependencies (including SAM3 requirements)
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    git \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    ffmpeg \
    curl \
    wget \
    python3.12 \
    python3-pip \
    python3.12-venv \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python3.12 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install SAM3 from official Meta AI repository
RUN git clone https://github.com/facebookresearch/sam3.git /opt/facebookresearch/sam3 && \
    cd /opt/facebookresearch/sam3 && \
    /opt/venv/bin/pip install --no-cache-dir -e .

# Copy pyproject.toml and install project dependencies
COPY pyproject.toml .
RUN /opt/venv/bin/pip install --no-cache-dir -e .

# Copy backend code
COPY . ./

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD /opt/venv/bin/python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

# Run the application
CMD ["/opt/venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
