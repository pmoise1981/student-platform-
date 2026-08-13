#!/usr/bin/env bash
set -euo pipefail
k3d cluster create student-platform -p "8081:80@loadbalancer" --agents 1
# Build the small student-facing FastAPI image and import it into k3d.
docker build -t student-platform-backend:local workloads/backend
k3d image import student-platform-backend:local -c student-platform
kubectl cluster-info --context k3d-student-platform
