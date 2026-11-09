#!/usr/bin/env python3
"""Inicia la entrada adicional de la API con el entorno ya instalado."""
import os
from pathlib import Path
import sys
import uvicorn

if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    os.chdir(root)
    sys.path.insert(0, str(root))
    uvicorn.run("backend.api.sdn_vivo_v1:app", host="127.0.0.1", port=8001)
