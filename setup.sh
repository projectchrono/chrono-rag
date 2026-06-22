#!/bin/bash
# Full first-time setup and launch for chrono-rag on Ubuntu 22.04.
# Re-running is safe: each step checks before acting.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_DIR="$HOME/local"
DOCKER_BIN="$LOCAL_DIR/docker-bin"
NODE_VERSION="22.16.0"
NODE_DIR="$LOCAL_DIR/node-v${NODE_VERSION}-linux-x64"
DOCKER_VERSION="27.5.1"

export PATH="$DOCKER_BIN:$NODE_DIR/bin:$HOME/.local/bin:$PATH"
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"

# ---------- 1. System packages (requires sudo) ----------
echo "==> Installing system packages (uidmap, slirp4netns)..."
sudo apt-get install -y uidmap slirp4netns

# ---------- 2. Python packages ----------
echo "==> Installing Python packages..."
pip3 install --user -r "$SCRIPT_DIR/requirements.txt"

# ---------- 3. Node.js ----------
if [ ! -x "$NODE_DIR/bin/node" ]; then
  echo "==> Downloading Node.js ${NODE_VERSION}..."
  mkdir -p "$LOCAL_DIR"
  curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" \
    -o /tmp/node.tar.xz
  tar -xf /tmp/node.tar.xz -C "$LOCAL_DIR"
  rm /tmp/node.tar.xz
fi
echo "    node $(node --version), npm $(npm --version)"

# ---------- 4. Rootless Docker ----------
if [ ! -x "$DOCKER_BIN/dockerd" ]; then
  echo "==> Downloading Docker ${DOCKER_VERSION} static binaries..."
  mkdir -p "$DOCKER_BIN"
  curl -fsSL "https://download.docker.com/linux/static/stable/x86_64/docker-${DOCKER_VERSION}.tgz" \
    -o /tmp/docker.tgz
  tar -xf /tmp/docker.tgz -C /tmp/
  cp /tmp/docker/* "$DOCKER_BIN/"
  rm -rf /tmp/docker /tmp/docker.tgz

  curl -fsSL "https://download.docker.com/linux/static/stable/x86_64/docker-rootless-extras-${DOCKER_VERSION}.tgz" \
    -o /tmp/docker-rootless-extras.tgz
  tar -xf /tmp/docker-rootless-extras.tgz -C /tmp/
  cp /tmp/docker-rootless-extras/* "$DOCKER_BIN/"
  rm -rf /tmp/docker-rootless-extras /tmp/docker-rootless-extras.tgz
  chmod +x "$DOCKER_BIN"/*
fi

if [ ! -x "$DOCKER_BIN/slirp4netns" ]; then
  echo "==> Downloading slirp4netns..."
  curl -fsSL -o "$DOCKER_BIN/slirp4netns" \
    "https://github.com/rootless-containers/slirp4netns/releases/download/v1.3.1/slirp4netns-x86_64"
  chmod +x "$DOCKER_BIN/slirp4netns"
fi

if [ ! -x "$DOCKER_BIN/fuse-overlayfs" ]; then
  echo "==> Downloading fuse-overlayfs..."
  curl -fsSL -o "$DOCKER_BIN/fuse-overlayfs" \
    "https://github.com/containers/fuse-overlayfs/releases/download/v1.14/fuse-overlayfs-x86_64"
  chmod +x "$DOCKER_BIN/fuse-overlayfs"
fi

# Configure Docker daemon to use fuse-overlayfs (avoids UID chown issues in rootless mode)
mkdir -p "$HOME/.config/docker"
cat > "$HOME/.config/docker/daemon.json" << 'EOF'
{
  "storage-driver": "fuse-overlayfs"
}
EOF

# Install and start rootless Docker daemon via systemd user service
if ! systemctl --user is-active --quiet docker.service 2>/dev/null; then
  echo "==> Setting up rootless Docker daemon..."
  XDG_RUNTIME_DIR="/run/user/$(id -u)" dockerd-rootless-setuptool.sh install
fi

if ! systemctl --user is-active --quiet docker.service; then
  echo "==> Starting Docker daemon..."
  systemctl --user start docker.service
  sleep 5
fi
echo "    Docker $(docker version --format '{{.Server.Version}}' 2>/dev/null)"

# ---------- 5. MongoDB Atlas Local ----------
if ! docker inspect atlas_local > /dev/null 2>&1; then
  echo "==> Pulling MongoDB Atlas Local image (this may take a few minutes)..."
  docker pull mongodb/mongodb-atlas-local
  docker run -d --name atlas_local \
    -p 27017:27017 \
    -v atlas_data:/data/db \
    -v atlas_mongot_data:/data/mongot \
    mongodb/mongodb-atlas-local:latest
elif ! docker ps --filter name=atlas_local --filter status=running -q | grep -q .; then
  echo "==> Starting existing MongoDB Atlas Local container..."
  docker start atlas_local
fi
echo "==> Waiting for MongoDB to be ready..."
for i in $(seq 1 30); do
  if python3 -c "
from pymongo import MongoClient
MongoClient('mongodb://localhost:27017/?directConnection=true', serverSelectionTimeoutMS=2000).server_info()
" 2>/dev/null; then
    break
  fi
  sleep 2
done
echo "    MongoDB ready"

# ---------- 6. Index data (first run only) ----------
# Start backend temporarily to run indexing, then keep it running
echo "==> Starting backend..."
kill "$(lsof -ti:8000)" 2>/dev/null || true
sleep 1
python3 -m uvicorn main:app --host 127.0.0.1 --port 8000 --app-dir "$SCRIPT_DIR/src" &
BACKEND_PID=$!

echo "==> Waiting for backend to start..."
for i in $(seq 1 15); do
  if curl -s http://localhost:8000/docs > /dev/null 2>&1; then break; fi
  sleep 1
done

# Check if the vector index already exists; index if not
INDEXED=$(python3 -c "
from pymongo import MongoClient
c = MongoClient('mongodb://localhost:27017/?directConnection=true')
col = c['chrono_rag']['chunks']
print(col.count_documents({}))
" 2>/dev/null)
if [ "${INDEXED:-0}" -eq 0 ]; then
  echo "==> Indexing PyChrono examples into MongoDB (this may take a few minutes)..."
  RESULT=$(curl -s -X POST http://localhost:8000/index)
  echo "    $RESULT"
else
  echo "    MongoDB already has ${INDEXED} chunks — skipping re-index"
fi

# ---------- 7. Frontend ----------
echo "==> Installing frontend dependencies..."
cd "$SCRIPT_DIR/frontend"
npm install

echo "==> Starting frontend..."
npm run dev &

LOCAL_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "============================================"
echo "  chrono-rag is running"
echo ""
echo "  This machine  : https://localhost:5173"
echo "  Local network : https://${LOCAL_IP}:5173"
echo "  Backend API   : http://localhost:8000"
echo "  MongoDB       : localhost:27017"
echo ""
echo "  Share https://${LOCAL_IP}:5173 with other"
echo "  machines on this network. Browsers will"
echo "  show a certificate warning on first visit"
echo "  — click 'Advanced' and proceed to accept"
echo "  the self-signed certificate."
echo "============================================"
echo "  Backend PID: $BACKEND_PID  (stop: kill $BACKEND_PID)"
echo "  Press Ctrl-C to stop the frontend"
wait
