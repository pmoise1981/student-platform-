#!/usr/bin/env bash
set -euo pipefail

if ! k3d cluster list | awk 'NR>1 {print $1}' | grep -qx student-platform; then
  k3d cluster create student-platform -p "8081:80@loadbalancer" --agents 1
fi

# These two local images are the actual student workspaces. They are imported into
# k3d so provisioning never depends on a private image registry during local use.
docker build -t student-platform-backend-workspace:local workloads/backend
docker build -t student-platform-data-workspace:local workloads/data
k3d image import student-platform-backend-workspace:local -c student-platform
k3d image import student-platform-data-workspace:local -c student-platform

kubectl cluster-info --context k3d-student-platform
