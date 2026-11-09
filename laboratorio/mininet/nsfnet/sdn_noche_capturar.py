#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Captura complementaria automatica NSFNET/GEANT2. Requiere Linux y Mininet."""
import csv
import json
import math
import os
import random
import signal
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone

from sdn_noche_comun import (Probes, SampleUnavailable, caracteristicas_lado, cpu, fecha, guardar_json,
    iso, mac, memoria, muestra_of, ocupacion, programar_rutas, qdisc, rutas, sysfs, union_us)


class Captura:
    def __init__(self, carpeta):
        self.carpeta = carpeta
        with open(os.path.join(carpeta, "config.json")) as f:
            self.cfg = json.load(f)
        self.base = self.cfg["rest_url"]
        self.inicio = time.monotonic()
        self.estado = {"estado": "iniciando", "ready": False, "inicio_utc": iso(), "pid": os.getpid(),
                       "carpeta": carpeta, "filas": 0, "cobertura_adicional_s": {}}
        self.intervalos = {t: set() for t in ("nsfnet", "geant2")}
        self.validado = set()
        self.semillas_usadas = set(self.cfg["forbidden_seeds"])
        self.errores = 0

    def publicar(self, estado=None, **datos):
        if estado:
            self.estado["estado"] = estado
        self.estado.update(datos)
        self.estado["actualizado_utc"] = iso()
        guardar_json(os.path.join(self.carpeta, "estado.json"), self.estado)
        print(iso(), self.estado["estado"], datos, flush=True)

    def ssh(self, argumentos, entrada=None):
        comando = ["ssh", "-S", self.cfg["ssh_socket"], "-o", "BatchMode=yes",
                   self.cfg["ryu_target"]] + argumentos
        return subprocess.check_output(comando, input=entrada, universal_newlines=True, timeout=180)

    def crear_red(self, nombre):
        from mininet.net import Mininet
        from mininet.node import RemoteController, OVSSwitch
        from mininet.link import TCLink
        from mininet.log import setLogLevel
        setLogLevel("warning")
        perfil = self.cfg["topologies"][nombre]
        for n in perfil["nodes"]:
            fisico = "ns"+n["switch"][1:]
            if os.path.exists("/sys/class/net/"+fisico):
                raise ValueError("Existe otra red de captura con interfaz " + fisico)
        net = Mininet(controller=None, switch=OVSSwitch, link=TCLink, autoSetMacs=False)
        self.net, self.hijos, self.logs, self.probes = net, [], [], None
        self.rx_paths = []
        sesion = tempfile.mkdtemp(prefix=nombre+"_", dir=self.carpeta)
        self.trafico = os.path.join(sesion, "trafico.json")
        guardar_json(self.trafico, {"version": 0, "flows": {}})
        net.addController("c0", controller=RemoteController, ip=self.cfg["ryu_ip"],
                          port=self.cfg["of_port"])
        switches = {}
        for n in perfil["nodes"]:
            switches[n["switch"]] = net.addSwitch("ns"+n["switch"][1:], dpid=n["dpid"],
                                                 protocols="OpenFlow13", failMode="secure")
        enlaces = []
        for e in perfil["links"]:
            link = net.addLink(switches[e["switch_u"]], switches[e["switch_v"]],
                port1=e["port_u"], port2=e["port_v"], bw=e["capacity_mbps"],
                delay="{}ms".format(e["configured_delay_ms"]), max_queue_size=e["queue_limit_packets"])
            copia = dict(e)
            copia.update(interface_u=link.intf1.name, interface_v=link.intf2.name)
            enlaces.append(copia)
        hosts = {}
        for n in perfil["nodes"]:
            h = net.addHost("nsh"+n["switch"][1:], ip=n["host_ip"], mac=mac(n["switch"]))
            net.addLink(h, switches[n["switch"]], port1=0, port2=n["host_port"], bw=1000, delay="0ms")
            hosts[n["switch"]] = h
        net.start()
        caminos = rutas(perfil)
        programar_rutas(self.base, perfil, caminos)
        net.staticArp()
        worker = os.path.join(os.path.dirname(__file__), "sdn_noche_trafico.py")
        for u, h in hosts.items():
            rx_path = os.path.join(sesion, u+"_rx.json")
            self.rx_paths.append(rx_path)
            for tipo, args in (("rx", ["rx", rx_path]), ("tx", ["tx", self.trafico, u])):
                log = open(os.path.join(sesion, u+"_"+tipo+".log"), "a")
                self.logs.append(log)
                self.hijos.append(h.popen([sys.executable, worker]+args,
                                         stdout=log, stderr=subprocess.STDOUT))
        self.probes = Probes(enlaces)
        self.probes.gracia = max(2.0, max(
            4*e["configured_delay_ms"]/1000.0 +
            2*e["queue_limit_packets"]*max(perfil["traffic_datagram_bytes"]+42, 1514)*8 /
            (e["capacity_mbps"]*1e6) for e in enlaces))
        guardar_json(os.path.join(sesion, "interfaces.json"), {"topologia": nombre, "links": enlaces})
        return perfil, enlaces, caminos

    def cerrar_red(self):
        if getattr(self, "probes", None):
            self.probes.close()
            self.probes = None
        for p in getattr(self, "hijos", []):
            if p.poll() is None:
                p.terminate()
        for p in getattr(self, "hijos", []):
            try:
                p.wait(timeout=4)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
        for log in getattr(self, "logs", []):
            log.close()
        if getattr(self, "net", None):
            self.net.stop()
            self.net = None

    def plan(self, perfil, caminos, escena, semilla, baja=False):
        niveles = [0.1, 0.45, 0.8, 1.2, 0.4, 0.0]
        nivel = 0.1 if baja else niveles[escena % len(niveles)]
        nodos = [n["switch"] for n in perfil["nodes"]]
        ips = {n["switch"]: n["host_ip"].split("/")[0] for n in perfil["nodes"]}
        rng = random.Random(semilla)
        carga = {(i, d): 0.0 for i in range(len(perfil["links"])) for d in ("u_to_v", "v_to_u")}
        pares = []
        hotspot = rng.choice(nodos)
        for u in nodos:
            candidatos = [v for v in nodos if v != u]
            v = hotspot if escena % 2 and hotspot != u else rng.choice(candidatos)
            pares.append((u, v))
            for _, _, i, d, _ in caminos[(u, v)]:
                carga[(i, d)] += 1.0
        maximo = max(carga[(i, d)]/e["capacity_mbps"] for i, e in enumerate(perfil["links"])
                     for d in ("u_to_v", "v_to_u"))
        tasa = nivel/maximo if maximo else 0.0
        for k in carga:
            carga[k] *= tasa
        flows = {u: {"ip": ips[v], "mbps": tasa, "bytes": perfil["traffic_datagram_bytes"]}
                 for u, v in pares}
        guardar_json(self.trafico, {"version": time.time(), "flows": flows})
        return carga, nivel

    def medir(self, perfil, enlaces, segundos, numero, carga):
        if time.monotonic()-self.inicio > 12*3600:
            raise ValueError("Limite de 12 h de ejecucion alcanzado; se conservan las capturas")
        if any(p.poll() is not None for p in self.hijos):
            raise ValueError("Un generador o receptor UDP se detuvo; revisar sus logs")
        interfaces = [e[k] for e in enlaces for k in ("interface_u", "interface_v")]
        inicio = iso()
        of_a = muestra_of(self.base, perfil)
        q_a = {i: qdisc(i) for i in interfaces}
        c_a, c_previo = cpu(), cpu()
        pico = [0.0]
        previa = [time.monotonic(), sysfs(interfaces)]
        recientes = {i: {"rx": [], "tx": []} for i in interfaces}

        def observar():
            actual_t, actual = time.monotonic(), sysfs(interfaces)
            dt = actual_t-previa[0]
            if dt <= 0:
                return
            for i in interfaces:
                for d in ("rx", "tx"):
                    diferencia = actual[i][d+"_bytes"]-previa[1][i][d+"_bytes"]
                    if diferencia < 0:
                        raise ValueError("Reinicio de interfaz " + i)
                    recientes[i][d].append(diferencia*8.0/dt/1e6)
            c = cpu()
            tasas = ocupacion(c_previo, c)
            pico[0] = max([pico[0]]+[v for k, v in tasas.items() if k != "cpu"])
            c_previo.clear()
            c_previo.update(c)
            previa[:] = [actual_t, actual]

        sondas, max_send_ms = self.probes.medir(segundos, numero, observar)
        observar()
        of_b = muestra_of(self.base, perfil)
        q_b = {i: qdisc(i) for i in interfaces}
        c_b = cpu()
        mem, swap = memoria()
        fin = iso()
        lados, features = {}, {}
        for i, e in enumerate(enlaces):
            f = {k: e[k] for k in ("capacity_mbps", "configured_delay_ms", "queue_limit_packets",
                                   "queue_budget_packets", "propagation_budget_packets")}
            f.update(offered_u_to_v_mbps=carga[(i, "u_to_v")], offered_v_to_u_mbps=carga[(i, "v_to_u")],
                     traffic_datagram_bytes=perfil["traffic_datagram_bytes"],
                     cpu_busy_fraction=ocupacion(c_a, c_b)["cpu"], mem_available_kb=mem,
                     cpu_peak_core_fraction=pico[0], swap_used_kb=swap)
            lados[i] = {}
            for lado in ("u", "v"):
                clave = (e["switch_"+lado], e["port_"+lado])
                interfaz = e["interface_"+lado]
                r = caracteristicas_lado(of_a[clave], of_b[clave], q_a[interfaz], q_b[interfaz],
                                          e["capacity_mbps"], recientes[interfaz])
                lados[i][lado] = r
                f.update({lado+"_"+k: v for k, v in r.items()})
            if set(f) != set(self.cfg["features"]) or not all(math.isfinite(float(v)) for v in f.values()):
                raise ValueError("La ventana no tiene los 60 predictores validos")
            features[i] = f
        return {"start": inicio, "end": fin, "features": features, "sides": lados,
                "probes": sondas, "instrumentation_max_send_call_ms": max_send_ms,
                "resource_warning": pico[0] >= 0.95}

    def validar(self, nombre):
        self.publicar("validando_"+nombre)
        try:
            perfil, enlaces, caminos = self.crear_red(nombre)
            carga, _ = self.plan(perfil, caminos, 0, 1200000000, baja=True)
            ventana = self.medir(perfil, enlaces, 2.0, 1, carga)
            for e in enlaces:
                for d in ("u_to_v", "v_to_u"):
                    medido = ventana["probes"][(e["link_id"], d)]["delay_avg_ms"]
                    if medido < 0.5*e["configured_delay_ms"]:
                        raise ValueError("La sonda parece evitar la cola configurada en " + e["link_id"])
                    if medido > e["configured_delay_ms"]+100:
                        raise ValueError("Latencia de calibracion excesiva en " + e["link_id"])
            recibidos = 0
            for ruta in self.rx_paths:
                if os.path.isfile(ruta):
                    with open(ruta) as f:
                        recibidos += json.load(f)["packets"]
            if recibidos == 0:
                raise ValueError("Las sondas responden pero no llega trafico UDP entre los hosts")
            # El fallo anterior solo aparecio con sobrecarga: tambien se comprueba
            # la fase maxima antes de declarar lista la captura desatendida.
            carga_alta, _ = self.plan(perfil, caminos, 3, 1200000001)
            presion = self.medir(perfil, enlaces, 5.0, 2, carga_alta)
            guardar_json(os.path.join(self.carpeta, "validacion_"+nombre+".json"), {
                "fecha": iso(), "enlaces": len(enlaces), "sondas_bidireccionales": True,
                "predictores": 60, "delay_kernel_rx": True, "carga_maxima_comprobada": 1.2,
                "rechazos_tx_enobufs": sum(s["tx_refused_enobufs"] for s in presion["probes"].values())})
            self.validado.add(nombre)
        finally:
            self.cerrar_red()

    def fase(self, nombre, escritor, archivo):
        self.publicar("preparando_"+nombre)
        cuota = self.cfg["quotas_s"][nombre]
        if cuota <= 0:
            return
        try:
            perfil, enlaces, caminos = self.crear_red(nombre)
            anterior, contador, escena = None, 0, -1
            fallos_seguidos = 0
            cobertura = 0.0
            while cobertura < cuota:
                if contador % 3 == 0:
                    escena += 1
                    fraccion = cobertura/cuota
                    particion = "train" if fraccion < 0.7 else ("validation" if fraccion < 0.85 else "test")
                    p = ("train", "validation", "test").index(particion)
                    semilla = (1000000000 if nombre == "nsfnet" else 1100000000)+p*10000000+escena
                    while str(semilla) in self.semillas_usadas:
                        semilla += 1
                    self.semillas_usadas.add(str(semilla))
                    run = "nocturna-{}-{}-{}-{}".format(self.cfg["id"], nombre, particion, escena)
                    carga, nivel = self.plan(perfil, caminos, escena, semilla)
                contador += 1
                try:
                    actual = self.medir(perfil, enlaces, 20.0, contador, carga)
                except SampleUnavailable as error:
                    fallos_seguidos += 1
                    anterior = None
                    guardar_json(os.path.join(self.carpeta, "ventana_descartada_{}_{}.json".format(nombre, contador)),
                        {"fecha": iso(), "error": str(error), "nivel_ofrecido": nivel,
                         "sondas": getattr(self.probes, "last_diagnostics", {})})
                    self.publicar("recuperando_"+nombre, ready=False, ventana_descartada=contador,
                                  motivo_ventana=str(error), fallos_seguidos=fallos_seguidos)
                    if fallos_seguidos >= 6:
                        raise ValueError("Seis ventanas sin mediciones validas; se conserva el avance para reanudar")
                    if fallos_seguidos >= 3:
                        carga, nivel = self.plan(perfil, caminos, escena, semilla, baja=True)
                        run += "-recuperacion-"+str(contador)
                    time.sleep(min(2**fallos_seguidos, 8))
                    continue
                fallos_seguidos = 0
                actual.update(run=run, partition=particion, seed=semilla, scene=escena, cycle=contador, level=nivel)
                if anterior is not None and anterior["run"] == actual["run"]:
                    for i, e in enumerate(enlaces):
                        fila = dict(anterior["features"][i])
                        fila.update(topologia=nombre.upper(), particion=anterior["partition"],
                            run_id=anterior["run"], scenario_id=anterior["run"], seed=anterior["seed"],
                            topology_id=perfil["source_topology_id"]+"-capture-v2", cycle=anterior["cycle"],
                            link_id=e["link_id"], switch_u=e["switch_u"], switch_v=e["switch_v"],
                            port_u=e["port_u"], port_v=e["port_v"], sample_status="ok", training_weight=1.0,
                            collection_segment="nocturna-v2", traffic_state_prev=str(anterior["level"]),
                            routing_metadata_corrected=True, resource_warning=anterior["resource_warning"],
                            feature_start=anterior["start"], feature_end=anterior["end"],
                            label_start=actual["start"], label_end=actual["end"],
                            target_window_actual_s=(fecha(actual["end"])-fecha(actual["start"])).total_seconds(),
                            target_throughput_u_to_v_mbps=actual["sides"][i]["v"]["rx_mbps"],
                            target_throughput_v_to_u_mbps=actual["sides"][i]["u"]["rx_mbps"],
                            measurement_method="af_packet_offered_probes_tx_status_kernel_rx_v3",
                            probe_loss_scope="offered_including_local_tx_refusals",
                            routing_policy="dijkstra_configured_delay_v2",
                            profile_source_run_id=perfil["source_run_id"],
                            instrumentation_max_send_call_ms=actual["instrumentation_max_send_call_ms"])
                        for d in ("u_to_v", "v_to_u"):
                            s = actual["probes"][(e["link_id"], d)]
                            for campo in ("loss_ratio", "delay_avg_ms"):
                                fila["target_"+d+"_"+campo] = s[campo]
                            for campo in ("sent", "received", "accepted", "tx_refused_enobufs", "tx_refused_busy",
                                          "post_accept_loss_ratio"):
                                fila["target_"+d+"_"+campo] = s[campo]
                        if any(actual["probes"][(e["link_id"], d)]["accepted"] <
                               actual["probes"][(e["link_id"], d)]["sent"] for d in ("u_to_v", "v_to_u")):
                            fila["sample_status"] = "ok_with_tx_refusals"
                        escritor.writerow(fila)
                        self.estado["filas"] += 1
                    archivo.flush()
                    os.fsync(archivo.fileno())
                    self.intervalos[nombre].update(((fecha(anterior["start"]), fecha(anterior["end"])),
                                                    (fecha(actual["start"]), fecha(actual["end"]))))
                    cobertura = union_us(self.intervalos[nombre])/1e6
                    self.estado["cobertura_adicional_s"][nombre] = cobertura
                    self.publicar("capturando_"+nombre, ready=len(self.validado) == 2,
                                  topologia=nombre, pendiente_fase_s=max(0.0, cuota-cobertura),
                                  rechazos_tx_ultima_ventana=sum(s["sent"]-s["accepted"]
                                      for s in actual["probes"].values()))
                anterior = actual
        finally:
            self.cerrar_red()

    def ejecutar(self):
        if fecha(iso()) <= fecha(self.cfg["baseline_last_label_end"]):
            raise ValueError("El reloj de Mininet no es posterior al dataset historico; revisar la hora antes de capturar")
        # Una comprobacion inicial de ambas redes evita dejar horas de captura sin sondas validas.
        for nombre in ("geant2", "nsfnet"):
            self.validar(nombre)
        ruta = os.path.join(self.carpeta, "captura_adicional.csv")
        columnas = list(dict.fromkeys(self.cfg["columns"]+[
            "measurement_method", "routing_policy", "profile_source_run_id",
            "instrumentation_max_send_call_ms", "target_u_to_v_sent", "target_u_to_v_received",
            "target_v_to_u_sent", "target_v_to_u_received", "probe_loss_scope"]+
            ["target_"+d+"_"+c for d in ("u_to_v", "v_to_u") for c in
             ("accepted", "tx_refused_enobufs", "tx_refused_busy", "post_accept_loss_ratio")]))
        with open(ruta, "x", newline="", encoding="utf-8") as archivo:
            escritor = csv.DictWriter(archivo, fieldnames=columnas)
            escritor.writeheader()
            for nombre in ("nsfnet", "geant2"):
                self.fase(nombre, escritor, archivo)
        self.publicar("consolidando_en_ryu")
        destino = self.cfg["ryu_target"]+":"+self.cfg["remote_dir"]+"/captura_adicional.csv"
        subprocess.check_call(["scp", "-o", "ControlPath="+self.cfg["ssh_socket"],
                               "-o", "BatchMode=yes", ruta, destino], timeout=300)
        respuesta = self.ssh(["python3", self.cfg["remote_dir"]+"/sdn_noche_ryu.py", "merge",
                              self.cfg["remote_dir"]])
        final = json.loads(respuesta)
        guardar_json(os.path.join(self.carpeta, "resultado_final.json"), final)
        self.publicar("completado", **final)


def main():
    if os.geteuid() != 0:
        raise ValueError("El capturador requiere sudo")
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    captura = Captura(os.path.abspath(sys.argv[1]))
    try:
        captura.ejecutar()
    except BaseException as error:
        captura.publicar("error", ready=False, error=str(error),
                         detalle="Las filas ya escritas permanecen en captura_adicional.csv")
        traceback.print_exc()
        captura.cerrar_red()
        raise
    finally:
        try:
            captura.ssh(["python3", captura.cfg["remote_dir"]+"/sdn_noche_ryu.py", "stop",
                         captura.cfg["remote_dir"]])
        except Exception as error:
            print("No se pudo cerrar el controlador dedicado:", error, flush=True)
        try:
            subprocess.call(["ssh", "-S", captura.cfg["ssh_socket"], "-O", "exit",
                             captura.cfg["ryu_target"]], stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
        except Exception:
            pass


if __name__ == "__main__":
    main()
