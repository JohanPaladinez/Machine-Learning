#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Utilidades para la captura adicional. Python 3.6, Linux."""
import csv
import ctypes
import errno
import heapq
import json
import math
import os
import re
import selectors
import socket
import struct
import subprocess
import time
import uuid
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen

CONTADORES = ["rx_bytes", "tx_bytes", "rx_packets", "tx_packets",
              "rx_dropped", "tx_dropped", "rx_errors", "tx_errors"]
ETH_PROBE = 0x88b5
HEADER = struct.Struct("!16sIIIQ")


class SampleUnavailable(ValueError):
    """Una ventana no permite medir los seis objetivos; no se incorpora al CSV ML."""


def enviar_sonda(sock, paquete):
    """Un rechazo local se registra; no equivale a un envio aceptado por el kernel."""
    try:
        cantidad = sock.send(paquete)
    except OSError as error:
        if error.errno == errno.ENOBUFS:
            return "enobufs"
        if error.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
            return "busy"
        raise
    if cantidad != len(paquete):
        raise ValueError("Envio incompleto de sonda Ethernet")
    return "accepted"


def resumen_sondas(ofrecidas, aceptadas, recibidas, rechazos):
    n, a, r = len(ofrecidas), len(aceptadas), len(recibidas)
    if not set(recibidas).issubset(ofrecidas) or not aceptadas.issubset(ofrecidas):
        raise ValueError("Secuencias de sondas inconsistentes")
    rx_aceptadas = len(set(recibidas) & aceptadas)
    return {"sent": n, "accepted": a, "received": r,
        "tx_refused_enobufs": rechazos["enobufs"], "tx_refused_busy": rechazos["busy"],
        "loss_ratio": None if n == 0 else (n-r)/float(n),
        "post_accept_loss_ratio": None if a == 0 else (a-rx_aceptadas)/float(a),
        "delay_avg_ms": None if r == 0 else sum(recibidas.values())/r}


def filtrar_sondas(sock):
    class Instruccion(ctypes.Structure):
        _fields_ = [("code", ctypes.c_ushort), ("jt", ctypes.c_ubyte),
                    ("jf", ctypes.c_ubyte), ("k", ctypes.c_uint32)]
    class Programa(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.POINTER(Instruccion))]
    instrucciones = (Instruccion*4)(
        Instruccion(0x28, 0, 0, 12), Instruccion(0x15, 0, 1, ETH_PROBE),
        Instruccion(0x06, 0, 0, 0xffffffff), Instruccion(0x06, 0, 0, 0))
    programa = Programa(4, instrucciones)
    sock.setsockopt(socket.SOL_SOCKET, 26, bytes(programa))  # SO_ATTACH_FILTER


def iso():
    return datetime.now(timezone.utc).isoformat()


def fecha(s):
    s = s.strip().replace("Z", "+00:00")
    if s[-3] == ":":
        s = s[:-3] + s[-2:]
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    raise ValueError("Fecha invalida: " + s)


def union_us(intervalos):
    ordenados = sorted(set(intervalos))
    if not ordenados:
        return 0
    inicio, fin = ordenados[0]
    total = 0
    unidad = timedelta(microseconds=1)
    for a, b in ordenados[1:]:
        if a <= fin:
            fin = max(fin, b)
        else:
            total += (fin - inicio) // unidad
            inicio, fin = a, b
    return total + (fin - inicio) // unidad


def guardar_json(ruta, objeto):
    parcial = ruta + ".tmp"
    with open(parcial, "w", encoding="utf-8") as f:
        json.dump(objeto, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(parcial, ruta)


def http(base, ruta, datos=None):
    cuerpo = None if datos is None else json.dumps(datos).encode("utf-8")
    req = Request(base + ruta, data=cuerpo, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=8) as respuesta:
        texto = respuesta.read().decode("utf-8")
    return json.loads(texto) if texto.strip() else None


def mac(n):
    s = "{:012x}".format(int(n[1:]))
    return ":".join(s[i:i+2] for i in range(0, 12, 2))


def rutas(perfil):
    ady = {n["switch"]: [] for n in perfil["nodes"]}
    for i, e in enumerate(perfil["links"]):
        costo = max(float(e["configured_delay_ms"]), 0.001)
        ady[e["switch_u"]].append((e["switch_v"], costo, i, "u_to_v", e["port_u"]))
        ady[e["switch_v"]].append((e["switch_u"], costo, i, "v_to_u", e["port_v"]))
    resultado = {}
    for origen in sorted(ady):
        dist, caminos, cola = {origen: 0.0}, {origen: []}, [(0.0, origen)]
        while cola:
            costo, u = heapq.heappop(cola)
            if costo != dist[u]:
                continue
            for v, peso, i, sentido, puerto in sorted(ady[u]):
                nuevo = costo + peso
                if v not in dist or nuevo < dist[v] - 1e-12:
                    dist[v] = nuevo
                    caminos[v] = caminos[u] + [(u, v, i, sentido, puerto)]
                    heapq.heappush(cola, (nuevo, v))
        if len(caminos) != len(ady):
            raise ValueError("Topologia desconectada")
        for destino, camino in caminos.items():
            resultado[(origen, destino)] = camino
    return resultado


def programar_rutas(base, perfil, caminos):
    esperados = {int(n["dpid"], 16) for n in perfil["nodes"]}
    limite = time.monotonic() + 60
    while True:
        vistos = set(map(int, http(base, "/stats/switches")))
        if vistos == esperados:
            break
        if time.monotonic() > limite:
            raise ValueError("RYU no registra todos los switches: {} de {}".format(len(vistos), len(esperados)))
        time.sleep(1)
    for nodo in perfil["nodes"]:
        u, dpid = nodo["switch"], int(nodo["dpid"], 16)
        # El controlador dedicado no instala flooding ni STP.
        http(base, "/stats/flowentry/add", {"dpid": dpid, "priority": 0,
             "match": {}, "actions": []})
        for destino in perfil["nodes"]:
            v = destino["switch"]
            puerto = nodo["host_port"] if u == v else caminos[(u, v)][0][4]
            http(base, "/stats/flowentry/add", {"dpid": dpid, "cookie": 1396985422,
                 "priority": 100, "match": {"dl_dst": mac(v)},
                 "actions": [{"type": "OUTPUT", "port": puerto}]})
    # Lectura posterior confirma que RYU/OVS aceptaron las reglas.
    for nodo in perfil["nodes"]:
        dpid = int(nodo["dpid"], 16)
        flujos = http(base, "/stats/flow/{}".format(dpid)).get(str(dpid), [])
        if sum(int(f.get("priority", 0)) == 100 for f in flujos) != len(perfil["nodes"]):
            raise ValueError("No se instalaron todas las rutas en " + nodo["switch"])


def muestra_of(base, perfil):
    resultado = {}
    for nodo in perfil["nodes"]:
        dpid = int(nodo["dpid"], 16)
        a = time.monotonic()
        datos = http(base, "/stats/port/{}".format(dpid))
        b = time.monotonic()
        for p in datos.get(str(dpid), []):
            # RYU puede devolver nombres como LOCAL para puertos especiales.
            # Las versiones que usan numeros hexadecimales tambien son validas.
            try:
                valor = p.get("port_no")
                numero = int(valor, 16) if isinstance(valor, str) and valor.lower().startswith("0x") else int(valor)
            except (ValueError, TypeError):
                continue
            if not 1 <= numero < 0xffffff00:
                continue
            valores = {k: int(p[k]) for k in CONTADORES}
            if any(v < 0 or v >= 2**63 for v in valores.values()):
                raise ValueError("Contador no soportado en {}:{}".format(nodo["switch"], numero))
            resultado[(nodo["switch"], numero)] = (0.5 * (a+b), valores)
    return resultado


def sysfs(interfaces):
    return {s: {c: int(open("/sys/class/net/{}/statistics/{}".format(s, c)).read())
                for c in ("tx_bytes", "rx_bytes")} for s in interfaces}


def cpu():
    datos = {}
    with open("/proc/stat") as f:
        for linea in f:
            if not linea.startswith("cpu"):
                break
            v = linea.split()
            n = list(map(int, v[1:9]))
            datos[v[0]] = (sum(n), n[3] + (n[4] if len(n) > 4 else 0))
    return datos


def ocupacion(a, b):
    r = {}
    for c in set(a) & set(b):
        total, idle = b[c][0]-a[c][0], b[c][1]-a[c][1]
        r[c] = 0.0 if total <= 0 else max(0.0, min(1.0, 1.0-idle/float(total)))
    return r


def memoria():
    with open("/proc/meminfo") as f:
        d = {l.split(":")[0]: int(l.split()[1]) for l in f if len(l.split()) >= 2}
    if "MemAvailable" not in d:
        raise ValueError("El kernel no informa MemAvailable")
    return d["MemAvailable"], d.get("SwapTotal", 0)-d.get("SwapFree", 0)


def qdisc(interfaz):
    comando = ["tc", "-s", "-j", "qdisc", "show", "dev", interfaz]
    p = subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         universal_newlines=True)
    salida, _ = p.communicate(timeout=8)
    if p.returncode == 0:
        try:
            candidatos = [q for q in json.loads(salida) if q.get("kind") == "netem"]
            if len(candidatos) == 1 and all(k in candidatos[0] for k in ("bytes", "packets", "drops", "backlog", "qlen")):
                q = candidatos[0]
                return dict(bytes=int(q["bytes"]), packets=int(q["packets"]), drops=int(q["drops"]),
                            backlog=int(q["backlog"]), qlen=int(q["qlen"]))
        except (ValueError, TypeError):
            pass
    salida = subprocess.check_output(["tc", "-s", "qdisc", "show", "dev", interfaz],
                                     universal_newlines=True, timeout=8)
    segmentos = re.split(r"(?m)(?=^qdisc )", salida)
    candidatos = [s for s in segmentos if s.startswith("qdisc netem ")]
    if len(candidatos) != 1:
        raise ValueError("No se identifica una sola cola netem en " + interfaz)
    s = candidatos[0]
    datos = re.search(r"Sent\s+(\d+)\s+bytes\s+(\d+)\s+pkt\s+\(dropped\s+(\d+)", s)
    cola = re.search(r"backlog\s+([\d.]+)([KMG]?b)\s+(\d+)p", s, re.I)
    if not datos or not cola:
        raise ValueError("Formato tc no reconocido en " + interfaz)
    factor = {"b": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3}[cola.group(2).lower()]
    return dict(bytes=int(datos.group(1)), packets=int(datos.group(2)), drops=int(datos.group(3)),
                backlog=int(float(cola.group(1))*factor), qlen=int(cola.group(3)))


def caracteristicas_lado(anterior, actual, qa, qb, capacidad, recientes):
    intervalo = actual[0]-anterior[0]
    if intervalo <= 0:
        raise ValueError("Intervalo OpenFlow no positivo")
    d = {k: actual[1][k]-anterior[1][k] for k in CONTADORES}
    q = {k: qb[k]-qa[k] for k in ("bytes", "packets", "drops")}
    if any(v < 0 for v in list(d.values())+list(q.values())):
        raise SampleUnavailable("Reinicio de contadores durante una ventana")
    r = {k+"_delta": v for k, v in d.items()}
    r["interval_s"] = intervalo
    for sentido in ("rx", "tx"):
        mbps = d[sentido+"_bytes"]*8.0/intervalo/1e6
        r[sentido+"_mbps"] = mbps
        r[sentido+"_load_ratio"] = mbps/capacidad
        r[sentido+"_pps"] = d[sentido+"_packets"]/intervalo
        valores = recientes.get(sentido, [])
        if not valores:
            raise ValueError("Faltan muestras recientes de " + sentido)
        media = sum(valores)/len(valores)
        r[sentido+"_mbps_short_std"] = math.sqrt(sum((v-media)**2 for v in valores)/len(valores))
        r[sentido+"_mbps_short_peak"] = max(valores)
    r.update(qdisc_drops_delta=q["drops"], qdisc_bytes_delta=q["bytes"],
             qdisc_packets_delta=q["packets"], queue_backlog_bytes=qb["backlog"], queue_packets=qb["qlen"])
    return r


class Probes:
    """Sondas por interfaz fisica, sin medir rutas entre hosts ni dividir RTT por dos."""
    def __init__(self, enlaces):
        self.selector = selectors.DefaultSelector()
        self.sockets, self.direcciones = {}, []
        self.nonce = uuid.uuid4().bytes
        try:
            for e in enlaces:
                for interfaz in (e["interface_u"], e["interface_v"]):
                    # ETH_P_ALL toma la copia antes del rx_handler de OVS. El
                    # filtro BPF evita recibir el trafico de fondo en Python.
                    s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0003))
                    filtrar_sondas(s)
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024*1024)
                    # SO_TIMESTAMPNS_OLD (35): struct timespec nativo en Linux Ubuntu.
                    s.setsockopt(socket.SOL_SOCKET, 35, 1)
                    s.bind((interfaz, 0))
                    s.setblocking(False)
                    self.sockets[interfaz] = s
                    self.selector.register(s, selectors.EVENT_READ, interfaz)
                for a, b, sentido in ((e["interface_u"], e["interface_v"], "u_to_v"),
                                      (e["interface_v"], e["interface_u"], "v_to_u")):
                    ma = bytes.fromhex(open("/sys/class/net/"+a+"/address").read().strip().replace(":", ""))
                    mb = bytes.fromhex(open("/sys/class/net/"+b+"/address").read().strip().replace(":", ""))
                    self.direcciones.append((a, b, mb+ma+struct.pack("!H", ETH_PROBE), e["link_id"], sentido))
        except Exception:
            self.close()
            raise

    def close(self):
        for s in self.sockets.values():
            s.close()
        self.selector.close()

    def medir(self, segundos, ventana, observar):
        for s in self.sockets.values():
            while True:
                try:
                    s.recv(4096)
                except BlockingIOError:
                    break
            s.getsockopt(263, 6, 8)  # PACKET_STATISTICS: reinicia el contador de descartes del receptor.
        enviados = [set() for _ in self.direcciones]
        aceptados = [set() for _ in self.direcciones]
        rechazados = [{"enobufs": 0, "busy": 0} for _ in self.direcciones]
        recibidos = [dict() for _ in self.direcciones]
        self.last_diagnostics = {}
        inicio, reloj = time.monotonic(), time.time()
        fin, siguiente, observacion = inicio+segundos, inicio, inicio+1.0
        # Se espera el drenaje de colas acotadas antes de declarar una sonda perdida.
        gracia = self.gracia
        max_send_ms = 0.0
        while time.monotonic() < fin+gracia:
            ahora = time.monotonic()
            if ahora < fin and ahora >= siguiente:
                for i, (a, b, cabecera, _, _) in enumerate(self.direcciones):
                    secuencia = len(enviados[i])
                    nanos = int(time.time()*1e9)
                    paquete = (cabecera+HEADER.pack(self.nonce, ventana, i, secuencia, nanos)).ljust(96, b"\0")
                    enviados[i].add(secuencia)
                    t = time.monotonic()
                    estado = enviar_sonda(self.sockets[a], paquete)
                    max_send_ms = max(max_send_ms, (time.monotonic()-t)*1000)
                    if estado == "accepted":
                        aceptados[i].add(secuencia)
                    else:
                        rechazados[i][estado] += 1
                siguiente = max(siguiente+0.1, time.monotonic())
            if ahora >= observacion:
                observar()
                observacion = time.monotonic()+1.0
            espera = min(0.05, max(0.0, siguiente-time.monotonic())) if ahora < fin else 0.05
            for clave, _ in self.selector.select(espera):
                while True:
                    try:
                        datos, mensajes, flags, addr = clave.fileobj.recvmsg(4096, 256)
                    except BlockingIOError:
                        break
                    if addr[2] == 4 or len(datos) < 14+HEADER.size:
                        continue
                    if flags & socket.MSG_CTRUNC:
                        raise ValueError("Timestamp truncado en el receptor de sondas")
                    nonce, w, i, seq, tx = HEADER.unpack(datos[14:14+HEADER.size])
                    if nonce != self.nonce or w != ventana or i >= len(self.direcciones):
                        continue
                    if clave.data != self.direcciones[i][1] or seq not in enviados[i]:
                        continue
                    rx = None
                    for nivel, tipo, cuerpo in mensajes:
                        if nivel == socket.SOL_SOCKET and tipo == 35 and len(cuerpo) >= struct.calcsize("@ll"):
                            s, ns = struct.unpack("@ll", cuerpo[:struct.calcsize("@ll")])
                            rx = s*1000000000+ns
                    if rx is None:
                        raise ValueError("Falta timestamp del kernel en la sonda recibida")
                    demora = (rx-tx)/1e6
                    if demora < 0:
                        raise ValueError("El reloj produjo una latencia negativa")
                    recibidos[i][seq] = demora
        if abs((time.time()-reloj)-(time.monotonic()-inicio)) > 0.005:
            raise SampleUnavailable("Salto del reloj durante la medicion")
        for s in self.sockets.values():
            _, drops = struct.unpack("@II", s.getsockopt(263, 6, 8))
            if drops:
                raise SampleUnavailable("El receptor local descarto sondas; no se etiqueta como perdida de red")
        resultado = {}
        for i, (_, _, _, enlace, sentido) in enumerate(self.direcciones):
            r = resumen_sondas(enviados[i], aceptados[i], recibidos[i], rechazados[i])
            resultado[(enlace, sentido)] = r
            self.last_diagnostics[enlace+" "+sentido] = r
        for (enlace, sentido), r in resultado.items():
            if r["sent"] < 5 or r["received"] == 0:
                raise SampleUnavailable("Sondas insuficientes en {} {}: {}/{}".format(
                    enlace, sentido, r["received"], r["sent"]))
        return resultado, max_send_ms
