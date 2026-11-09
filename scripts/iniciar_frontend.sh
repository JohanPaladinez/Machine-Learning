#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../frontend/app"
if ! command -v node >/dev/null; then
  export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
fi
exec node node_modules/.bin/vite preview --config vite.sdn-selector.config.js --outDir "${SDN_DIST_DIR:-dist-rutas-ml}" --host 127.0.0.1 --port "${SDN_FRONTEND_PORT:-5181}" --strictPort
