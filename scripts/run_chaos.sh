#!/usr/bin/env bash

echo "============================================="
echo " Phase 19: Rapid Sandbox & Chaos Orchestrator"
echo "============================================="

# Ensure Docker environment is up and natively built
echo "-> Building Docker ecosystem with Blackwell Architectures..."
docker-compose up --build -d

echo "-> Waiting 10 seconds for orchestrator health checks..."
sleep 10

# Execute Chaos script in the background
echo "-> Triggering 2-Hour Chaos sequence..."
python scripts/chaos_test.py &

echo "============================================="
echo " System Online. Chaos sequence active."
echo " Watch telemetry via: docker-compose logs -f"
echo "============================================="
