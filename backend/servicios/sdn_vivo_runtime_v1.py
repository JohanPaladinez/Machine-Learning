"""Une la observacion de Mininet con la identidad de los puertos OpenFlow de RYU."""
import hashlib
import ipaddress
import json
import os
import threading
import time
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener


def private_url(value):
    parsed = urlsplit(str(value).strip())
    if parsed.scheme not in ("http", "https") or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise ValueError("Usa http://IP:puerto sin credenciales, rutas ni parametros.")
    try:
        address = ipaddress.ip_address(parsed.hostname or "")
        port = parsed.port
    except ValueError:
        raise ValueError("Usa la IP privada de la VM y su puerto.")
    if not (address.is_private or address.is_loopback) or address.is_unspecified or address.is_multicast or not port or not 1 <= port <= 65535:
        raise ValueError("Se requiere una IP privada concreta y un puerto valido.")
    return parsed.geturl().rstrip("/")


def fetch_json(url):
    # La conexion entre las VMs se realiza directamente, sin un proxy externo.
    with build_opener(ProxyHandler({})).open(url, timeout=3) as response:
        data = response.read(4 * 1024 * 1024 + 1)
    if len(data) > 4 * 1024 * 1024:
        raise ValueError("Respuesta demasiado grande")
    return json.loads(data.decode("utf-8"))


def integer(value):
    return int(value, 16) if isinstance(value, str) and value.lower().startswith("0x") else int(value)


class LiveNetwork:
    def __init__(self, transport=fetch_json):
        self.transport = transport
        self.lock = threading.RLock()
        self.source_url = ""
        self.ryu_override = ""
        self.cached = None
        self.cached_at = 0
        self.ports_cache = {}
        source = os.environ.get("SDN_MININET_URL", "")
        if source:
            self.configure(source, os.environ.get("SDN_RYU_REST_URL", ""))

    def configure(self, source, ryu_override=""):
        source = private_url(source)
        override = private_url(ryu_override) if ryu_override.strip() else ""
        with self.lock:
            self.source_url, self.ryu_override = source, override
            self.cached, self.cached_at, self.ports_cache = None, 0, {}
        return {"source_url": source, "ryu_rest_override": override}

    def snapshot(self, force=False):
        with self.lock:
            now = time.monotonic()
            if not force and self.cached is not None and now - self.cached_at < 5:
                return self.cached
            result = self._snapshot(now, force)
            self.cached, self.cached_at = result, time.monotonic()
            return result

    def _snapshot(self, now, force=False):
        result = {"schema_version": 1, "ready": False, "status": "unconfigured", "source_url": self.source_url,
                  "ryu_rest_override": self.ryu_override, "ryu": {"status": "not_checked"}, "links_runtime": []}
        if not self.source_url:
            result["message"] = "Conecta la URL que imprime el observador de Mininet."
            return result
        try:
            observed = self.transport(self.source_url + "/snapshot")
            if observed.get("schema_version") != 1 or observed.get("observer_version") != "sdn-vivo-1":
                raise ValueError("El servicio no es el observador esperado")
        except Exception as error:
            result.update(status="mininet_unreachable", message="No se puede leer Mininet: " + str(error))
            return result
        for key in ("observed_utc", "capture", "candidates", "errors", "session_id", "source_kind", "topologia", "topology_document", "topology_instance_id", "metrics", "controller", "links_runtime"):
            if key in observed:
                result[key] = observed[key]
        if observed.get("status") != "observed":
            result.update(status=observed.get("status", "source_error"), message=observed.get("message", "No hay una red registrada activa."))
            return result
        try:
            controller = observed["controller"]
            # En captura manda el puerto guardado por el lanzador, nunca un 8080 supuesto.
            rest = controller.get("rest_url") or self.ryu_override
            if not rest:
                result.update(status="ryu_unconfigured", message="Esta sesion manual no publica su REST de RYU. Indicalo al conectar Mininet.")
                return result
            rest = private_url(rest)
            if ipaddress.ip_address(urlsplit(rest).hostname) != ipaddress.ip_address(controller["ip"]):
                raise ValueError("La IP del REST de RYU no corresponde al controlador de esta red")
            name = observed["topologia"]
            profile = observed["topology_document"]["topologies"][name]
            nodes = {n["switch"]: n for n in profile["nodes"]}
            expected = {int(n["dpid"], 16) for n in nodes.values()}
            connected = set(map(integer, self.transport(rest + "/stats/switches")))
            result["ryu"] = {"status": "connected", "rest_url": rest, "connected_dpids": sorted(connected),
                             "expected_dpids": sorted(expected), "identity_verified": False}
            missing = expected - connected
            if missing:
                result.update(status="waiting_ryu", message="Esperando switches de esta red en RYU: " + ", ".join(map(str, sorted(missing))))
                self.ports_cache.clear()
                return result
            identity = (rest, observed["topology_instance_id"], tuple(sorted(connected)))
            cached_ports = self.ports_cache.get(identity)
            if cached_ports and now - cached_ports[0] < 30 and not force:
                ports = cached_ports[1]
                port_time = cached_ports[0]
            else:
                port_time = now
                ports = {}
                for switch, node in nodes.items():
                    dpid = int(node["dpid"], 16)
                    entries = self.transport(rest + "/stats/portdesc/" + str(dpid)).get(str(dpid), [])
                    for p in entries:
                        try:
                            port_no = integer(p["port_no"])
                            if not 1 <= port_no < 0xffffff00:
                                continue
                            ports[(switch, port_no)] = {"name": str(p["name"]).rstrip("\x00"),
                                                        "config": integer(p["config"]), "state": integer(p["state"])}
                        except (TypeError, ValueError, KeyError):
                            continue
                self.ports_cache = {identity: (now, ports)}
            states = []
            identity_valid = True
            for switch, node in nodes.items():
                host_port = int(node["host_port"])
                host = ports.get((switch, host_port))
                physical = node.get("runtime_switch", switch)
                identity_valid = identity_valid and host is not None and host["name"] == "{}-eth{}".format(physical, host_port)
            for edge in observed["links_runtime"]:
                a = ports.get((edge["source"], edge["port_u"]))
                b = ports.get((edge["target"], edge["port_v"]))
                matched = a is not None and b is not None and a["name"] == edge["u"]["name"] and b["name"] == edge["v"]["name"]
                # Un enlace retirado es una caida; una interfaz existente con otro nombre es otro controlador.
                identity_valid = identity_valid and all(not side["exists"] or (port is not None and port["name"] == side["name"])
                                                         for side, port in ((edge["u"], a), (edge["v"], b)))
                # OFPPC_PORT_DOWN y OFPPS_LINK_DOWN son el bit 0 en OpenFlow 1.3.
                of_up = matched and not ((a["state"] | b["state"]) & 3) and not ((a["config"] | b["config"]) & 37)
                state = "up" if edge["linux_state"] == "up" and of_up else "down"
                states.append(dict(edge, openflow_identity_verified=matched, state=state))
            result["links_runtime"] = states
            result["ryu"]["identity_verified"] = bool(identity_valid)
            result["ryu"]["port_description_age_s"] = round(now - port_time, 2)
            if not identity_valid:
                result.update(status="controller_mismatch", message="Los DPID aparecen, pero sus puertos no coinciden con las interfaces de esta sesion de Mininet.")
                return result
            version = [observed["topology_instance_id"], sorted(connected), [(e["id"], e["state"]) for e in states]]
            result["graph_version"] = hashlib.sha256(json.dumps(version, sort_keys=True).encode()).hexdigest()[:24]
            result.update(status="active", ready=True, message="Red de Mininet y puertos de RYU verificados." )
        except Exception as error:
            result.update(status="ryu_unreachable", message="No se pudo verificar el controlador de esta red: " + str(error))
            result["ryu"]["status"] = "unreachable"
        return result


def route_inputs(snapshot, session_id, graph_version, origin, destination, policy, capacity_cost):
    if not snapshot.get("ready"):
        raise ValueError("No hay una red activa verificada para calcular la ruta.")
    if snapshot.get("topology_instance_id") != session_id or snapshot.get("graph_version") != graph_version:
        raise ValueError("La red cambio. Actualiza el estado y vuelve a calcular.")
    profile = snapshot["topology_document"]["topologies"][snapshot["topologia"]]
    nodes = [n["switch"] for n in profile["nodes"]]
    if origin not in nodes or destination not in nodes or origin == destination:
        raise ValueError("Selecciona dos nodos distintos de la red activa.")
    usable = {e["id"] for e in snapshot["links_runtime"] if e.get("state") == "up"}
    edges = []
    for e in profile["links"]:
        if e["link_id"] not in usable:
            continue
        if policy == "hops":
            cost = 1.0
        elif policy == "delay":
            cost = float(e["configured_delay_ms"])
        elif policy == "capacity":
            cost = capacity_cost(float(e["capacity_mbps"]))
        else:
            raise ValueError("Criterio no admitido")
        edges.append({"origen": e["switch_u"], "destino": e["switch_v"], "costo": cost})
    return {"nodos": nodes, "enlaces": edges, "origen": origin, "destino": destination, "dirigido": False}
