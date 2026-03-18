Write-Host "Installing grpcio-tools in Virtual Environment..."
python -m pip install grpcio-tools

Write-Host "Compiling Protobuf contracts..."
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. contracts/trades.proto
Write-Host "Done."
