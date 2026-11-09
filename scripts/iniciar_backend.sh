#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
exec .venv/bin/python -m uvicorn backend.api.sdn_selector_v2:app --host 127.0.0.1 --port "${SDN_API_PORT:-8002}"
