#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if ! command -v node >/dev/null; then
  export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
fi
export VITE_SDN_SELECTOR_API_URL="${VITE_SDN_SELECTOR_API_URL:-http://127.0.0.1:8002}"
cd frontend/app
node node_modules/.bin/vite build --config vite.sdn-selector.config.js --outDir "${SDN_DIST_DIR:-dist-rutas-ml}"
