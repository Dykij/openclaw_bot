# Install GPU Dependencies for Blackwell RTX 5060 Ti (sm_120) with CUDA 12.8

Write-Host "Setting up environment variables for CUDA 12.8 & sm_120..."
$env:CMAKE_ARGS = "-DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=120"
$env:FORCE_CMAKE = "1"
$env:NVCC_ARGS = "-gencode=arch=compute_120,code=sm_120"

# Note: The system needs to have CUDA 12.8 Toolkit installed before running this.

Write-Host "Installing pip dependencies..."
pip install --upgrade pip

Write-Host "Installing PyTorch for CUDA 12.8..."
# As of early 2026, nightly or specific wheel may be needed for CUDA 12.8 
# Replace with the exact index-url when official 12.8 builds stabilize
pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128

Write-Host "Building CuPy from source for sm_120..."
pip install cupy --no-binary cupy -v

Write-Host "Building llama-cpp-python with Flash Attention 2 and sm_120..."
$env:CMAKE_ARGS = "-DGGML_CUDA=on -DGGML_CUDA_FA=on -DCMAKE_CUDA_ARCHITECTURES=120"
pip install llama-cpp-python --no-cache-dir --verbose

Write-Host "Installing vLLM (with NVFP4/MXFP4 support)..."
pip install vllm>=0.12.0

Write-Host "GPU dependencies installed successfully for Phase 14."
