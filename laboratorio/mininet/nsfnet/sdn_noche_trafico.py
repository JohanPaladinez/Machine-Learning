#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UDP en los namespaces Mininet. Solo se ejecuta como hijo del capturador."""
import json
import os
import socket
import sys
import time


def main():
    modo = sys.argv[1]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4*1024*1024)
    if modo == "rx":
        sock.bind(("0.0.0.0", 5001))
        sock.settimeout(0.5)
        ruta = sys.argv[2]
        paquetes, consulta = 0, 0.0
        while True:
            try:
                sock.recvfrom(65535)
                paquetes += 1
            except socket.timeout:
                pass
            if time.monotonic() >= consulta:
                with open(ruta+".tmp", "w") as f:
                    json.dump({"packets": paquetes}, f)
                os.replace(ruta+".tmp", ruta)
                consulta = time.monotonic()+1.0
    ruta, host = sys.argv[2:4]
    sock.setblocking(False)
    previo, consulta, credito, version = time.monotonic(), 0.0, 0.0, None
    flujo = None
    while True:
        ahora = time.monotonic()
        if ahora >= consulta:
            with open(ruta) as f:
                config = json.load(f)
            if config["version"] != version:
                version, flujo = config["version"], config["flows"].get(host)
                credito = 0.0
            consulta = ahora+0.2
        if not flujo or flujo["mbps"] <= 0:
            previo = ahora
            time.sleep(0.02)
            continue
        tamano = flujo["bytes"]
        credito = min(credito+(ahora-previo)*flujo["mbps"]*1e6/8, max(tamano, tamano*8))
        previo = ahora
        while credito >= tamano:
            try:
                sock.sendto(b"T"*tamano, (flujo["ip"], 5001))
            except (BlockingIOError, OSError):
                break
            credito -= tamano
        time.sleep(0.002)


if __name__ == "__main__":
    main()
