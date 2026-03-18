# --- Stage 1: Build & Compile ---
FROM nvidia/cuda:12.8.0-devel-ubuntu24.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    python3.12 python3.12-venv python3.12-dev python3-pip \
    git cmake build-essential wget \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1

# CUDA Environment for Blackwell sm_120
ENV CUDA_HOME=/usr/local/cuda
ENV CMAKE_CUDA_ARCHITECTURES=120
ENV PATH="/usr/local/cuda/bin:${PATH}"

WORKDIR /build
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -U pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Blackwell-specific high-performance compilation
RUN CMAKE_ARGS="-DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=120" pip install --force-reinstall --no-cache-dir llama-cpp-python
RUN pip uninstall -y cupy-cuda12x && \
    NVCC_ARGS="-gencode=arch=compute_120,code=sm_120" pip install --no-cache-dir cupy

# --- Stage 2: Final Runtime ---
FROM nvidia/cuda:12.8.0-runtime-ubuntu24.04

# Core production environment
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y python3.12 python3-pip libgomp1 && \
    rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1

# Security: Create non-root user
RUN groupadd -r clawgroup && useradd -r -g clawgroup -s /sbin/nologin clawworker

# Copy virtualenv and app
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH="/app"

WORKDIR /app
COPY . .

# Set permissions
RUN chown -R clawworker:clawgroup /app /opt/venv

USER clawworker

# Entrypoint maps directly to the Orchestrator
CMD ["/opt/venv/bin/python3", "src/main.py"]
