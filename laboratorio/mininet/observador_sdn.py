#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Observador de solo lectura. Python 3.6+, sin sondas ni cambios a Mininet/RYU."""
import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import signal
import socket
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn

VERSION = "sdn-vivo-1"


def utc():
    return datetime.now(timezone.utc).isoformat()


def date(value):
    value = value.replace("Z", "+00:00")
    if value[-3:-2] == ":":
        value = value[:-3] + value[-2:]
    for pattern in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(value, pattern)
        except ValueError:
            pass
    raise ValueError("Fecha no reconocida")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:24]


def read_json(path):
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("Documento demasiado grande")
    return json.loads(path.read_text(encoding="utf-8"))


class Observer:
    def __init__(self, project, sysfs="/sys/class/net", proc="/proc"):
        self.project = Path(project).resolve()
        self.sysfs, self.proc = Path(sysfs), Path(proc)

    def process(self, pid, marker, argument=None):
        try:
            args = (self.proc / str(int(pid)) / "cmdline").read_bytes().decode().split("\0")
            return any(Path(a).name == marker for a in args) and (argument is None or argument in args)
        except (OSError, ValueError, UnicodeError):
            return False

    def interface(self, name):
        if not re.fullmatch(r"[a-zA-Z0-9_.:-]{1,32}", name):
            raise ValueError("Nombre de interfaz invalido")
        path = self.sysfs / name
        try:
            return {"name": name, "exists": True, "ifindex": int((path / "ifindex").read_text()),
                    "iflink": int((path / "iflink").read_text()),
                    "admin_up": bool(int((path / "flags").read_text().strip(), 0) & 1),
                    "operstate": (path / "operstate").read_text().strip()}
        except (OSError, ValueError):
            return {"name": name, "exists": False, "ifindex": None, "iflink": None, "admin_up": None, "operstate": "unknown"}

    def candidate(self, session, name, profile, interfaces, controller, capture=None, csv_path=None):
        if name not in ("nsfnet", "geant2") or not profile.get("nodes") or not profile.get("links"):
            raise ValueError("Perfil de topologia invalido")
        if len(profile["nodes"]) > 128 or len(profile["links"]) > 512:
            raise ValueError("Perfil de topologia demasiado grande")
        runtime = []
        for edge in interfaces:
            a, b = self.interface(edge["interface_u"]), self.interface(edge["interface_v"])
            peers = a["exists"] and b["exists"] and a["iflink"] == b["ifindex"] and b["iflink"] == a["ifindex"]
            up = peers and a["admin_up"] and b["admin_up"] and a["operstate"] == "up" and b["operstate"] == "up"
            runtime.append({"id": edge["link_id"], "source": edge["switch_u"], "target": edge["switch_v"],
                            "port_u": int(edge["port_u"]), "port_v": int(edge["port_v"]),
                            "u": a, "v": b, "peer_verified": bool(peers),
                            "linux_state": "up" if up else ("down" if peers else "missing")})
        if not any(e["u"]["exists"] or e["v"]["exists"] for e in runtime):
            return None
        clean = json.loads(json.dumps(profile))
        is_capture = capture is not None
        for node in clean["nodes"]:
            physical = ("nc" + node["switch"][1:]) if is_capture else node["switch"]
            node["runtime_switch"] = physical
            if is_capture:
                node["host"] = "nh" + node["switch"][1:]
        # Los puertos e interfaces observados proceden del lanzamiento, no del numero de nodos.
        identity = [session, name, controller, [(e["id"], e["u"]["ifindex"], e["v"]["ifindex"]) for e in runtime]]
        return {"session_id": session, "topology_instance_id": digest(identity), "topologia": name,
                "topology_document": {"schema_version": 1, "topologies": {name: clean}},
                "controller": controller, "links_runtime": runtime,
                "capture": capture,
                "metrics": self.metrics(csv_path, name, profile, capture) if csv_path else {"status": "unavailable", "links": {}},
                "source_kind": "capture" if is_capture else "manual"}

    def metrics(self, path, name, profile, capture):
        empty = {"status": "unavailable", "links": {}, "window_start": None, "window_end": None, "age_s": None}
        try:
            with Path(path).open("rb") as file:
                header = file.readline().decode("utf-8").strip()
                first = file.tell()
                file.seek(0, 2)
                end = file.tell()
                offset = max(first, end - 512 * 1024)
                file.seek(offset)
                if offset > first:
                    file.readline()  # Una fila cortada al principio no es una muestra.
                tail = file.read(512 * 1024)
            tail = tail[:tail.rfind(b"\n") + 1]  # Nunca publicar una fila aun en escritura.
            rows = csv.DictReader(io.StringIO(header + "\n" + tail.decode("utf-8")))
            expected = {str(e["link_id"]): e for e in profile["links"]}
            groups = {}
            for row in rows:
                if None in row or row.get("topologia", "").lower() != name:
                    continue
                # No se confunde una muestra recuperada de otra ejecucion con la actual.
                if not row.get("run_id", "").startswith("nocturna-" + capture["campaign_id"] + "-"):
                    continue
                key = (row.get("run_id"), row.get("cycle"), row.get("label_start"), row.get("label_end"))
                link_id = row.get("link_id")
                if link_id not in expected:
                    continue
                edge = expected[link_id]
                if (row.get("switch_u"), row.get("switch_v"), row.get("port_u"), row.get("port_v")) != (edge["switch_u"], edge["switch_v"], str(edge["port_u"]), str(edge["port_v"])):
                    continue
                group = groups.setdefault(key, {})
                if link_id in group:
                    group[link_id] = None
                else:
                    group[link_id] = row
            for key, group in reversed(list(groups.items())):
                if set(group) != set(expected) or any(row is None for row in group.values()):
                    continue
                result = {}
                try:
                    for link_id, row in group.items():
                        directions = {}
                        for direction in ("u_to_v", "v_to_u"):
                            values = {"throughput_mbps": float(row["target_throughput_" + direction + "_mbps"]),
                                      "delay_ms": float(row["target_" + direction + "_delay_avg_ms"]),
                                      "loss_ratio": float(row["target_" + direction + "_loss_ratio"])}
                            if not all(math.isfinite(v) and v >= 0 for v in values.values()) or values["loss_ratio"] > 1:
                                raise ValueError("Metrica invalida")
                            for field in ("sent", "accepted", "received", "tx_refused_enobufs", "tx_refused_busy"):
                                raw = row.get("target_" + direction + "_" + field, "")
                                values[field] = int(raw) if raw else None
                            directions[direction] = values
                        result[link_id] = {"directions": directions, "method": row.get("measurement_method"),
                                           "loss_scope": row.get("probe_loss_scope")}
                    age = (datetime.now(timezone.utc) - date(key[3])).total_seconds()
                    return {"status": "fresh" if 0 <= age <= 120 else "stale", "links": result,
                            "window_start": key[2], "window_end": key[3], "age_s": round(age, 2),
                            "source": "captura_adicional.csv", "note": "Ultima ventana completa; Loss ofrecido incluye rechazos locales de TX cuando asi lo declara loss_scope."}
                except (ValueError, TypeError, KeyError):
                    continue
        except (OSError, ValueError, UnicodeError, csv.Error):
            pass
        return empty

    def snapshot(self):
        candidates, captures, errors = [], [], []
        for state_path in self.project.glob("nocturna_*/estado.json"):
            try:
                state = read_json(state_path)
                folder = state_path.parent
                alive = self.process(state.get("pid"), "sdn_noche_capturar.py", str(folder))
                record = {"state": state.get("estado"), "updated_utc": state.get("actualizado_utc"),
                          "alive": alive, "rows": state.get("filas"), "coverage_s": state.get("cobertura_adicional_s", {}),
                          "session_id": folder.name, "error": state.get("error")}
                captures.append(record)
                match = re.fullmatch(r"(?:capturando|preparando|validando|recuperando)_(nsfnet|geant2)", str(state.get("estado")))
                if not alive or not match:
                    continue
                cfg = read_json(folder / "config.json")
                name = match.group(1)
                profile = cfg["topologies"][name]
                record["campaign_id"] = str(cfg["id"])
                interfaces = [dict(e, interface_u="nc{}-eth{}".format(e["switch_u"][1:], e["port_u"]),
                                   interface_v="nc{}-eth{}".format(e["switch_v"][1:], e["port_v"])) for e in profile["links"]]
                candidate = self.candidate(folder.name, name, profile, interfaces,
                    {"ip": cfg["ryu_ip"], "of_port": cfg["of_port"], "rest_url": cfg["rest_url"]},
                    record, folder / "captura_adicional.csv")
                if candidate:
                    candidates.append(candidate)
            except (OSError, ValueError, TypeError, KeyError) as error:
                errors.append("No se pudo interpretar una sesion de captura: " + str(error))
        paths = list(self.project.glob("*/sesion_*/topologia_activa.json")) + list(self.project.glob("sesion_*/topologia_activa.json"))
        for path in paths:
            try:
                if (path.parent / "sesion_cerrada.json").exists():
                    continue
                runtime = read_json(path)
                if not self.process(runtime.get("pid"), "topologia_dual_sdn.py"):
                    continue
                candidate = self.candidate(path.parent.name, runtime["topologia"].lower(), runtime["profile"],
                                           runtime["links"], dict(runtime["controller"], rest_url=None))
                if candidate:
                    candidates.append(candidate)
            except (OSError, ValueError, TypeError, KeyError) as error:
                errors.append("No se pudo interpretar una sesion manual: " + str(error))
        captures.sort(key=lambda c: c.get("updated_utc") or "", reverse=True)
        base = {"schema_version": 1, "observer_version": VERSION, "observed_utc": utc(),
                "capture": captures[0] if captures else None, "errors": errors,
                "read_only": True, "candidates": [{"session_id": c["session_id"], "topologia": c["topologia"]} for c in candidates]}
        if len(candidates) == 1:
            base.update(candidates[0], status="observed")
        elif len(candidates) > 1:
            base.update(status="ambiguous", message="Hay varias redes registradas activas. No se elige una por su numero de nodos.")
        else:
            unmanaged = any(re.fullmatch(r"(?:nc|s)\d+", p.name) for p in self.sysfs.glob("*"))
            base.update(status="unregistered" if unmanaged else "inactive",
                        message="Hay interfaces de Mininet sin una sesion registrada activa." if unmanaged else "No hay una topologia registrada activa.")
        return base


class ThreadServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def serve(observer, bind, port):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                data, code = {"status": "ok", "observer_version": VERSION, "read_only": True}, 200
            elif self.path == "/snapshot":
                try:
                    data, code = observer.snapshot(), 200
                except Exception:
                    data, code = {"status": "error", "message": "No se pudo leer el estado de Mininet."}, 503
            else:
                data, code = {"detail": "Ruta no disponible"}, 404
            body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    server = ThreadServer((bind, port), Handler)
    print("OBSERVADOR EN MARCHA · puerto {} · solo lectura".format(port), flush=True)
    # connect UDP elige direccion local; no se envia ningun datagrama.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("192.168.56.108", 9))
            print("URL PARA EL PANEL: http://{}:{}".format(sock.getsockname()[0], port), flush=True)
    except OSError:
        print("Usa la IP de Mininet accesible desde la VM de la interfaz y este puerto.", flush=True)
    server.serve_forever(poll_interval=0.5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proyecto", default=os.path.expanduser("~/proyecto_nsfnet"))
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--puerto", type=int, default=8766)
    args = parser.parse_args()
    if not 1024 <= args.puerto <= 65535:
        parser.error("Puerto invalido")
    serve(Observer(args.proyecto), args.bind, args.puerto)
