#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Pull docker image for mongodb atlas vector db.
docker pull mongodb/mongodb-atlas-local
docker run -d --name atlas_local --restart unless-stopped \
  -p 27017:27017 \
  -v atlas_data:/data/db \
  -v atlas_mongot_data:/data/mongot \
  mongodb/mongodb-atlas-local:latest

# Setup frontend (run in background)
cd "$SCRIPT_DIR/frontend" && npm install && npm run dev &

# Setup backend conda environment
conda create -n chrono python=3.12 -y

# Source conda so it is usable within this script
source "$(conda info --base)/etc/profile.d/conda.sh"

# Install pychrono into the environment
conda install -n chrono projectchrono::pychrono -c conda-forge -y

# Install pip packages (conda channels don't carry these)
conda run -n chrono pip install -r "$SCRIPT_DIR/requirements.txt"

# Run the backend
conda run -n chrono python "$SCRIPT_DIR/src/main.py"
