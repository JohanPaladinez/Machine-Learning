from fastapi import APIRouter, HTTPException, Query
import backend.api.sdn_vivo_v1 as live_api
from backend.servicios.operacion_sdn import OperationalReader

router = APIRouter(prefix='/api/sdn/operacion', tags=['Inspeccion de solo lectura'])
reader = OperationalReader()


@router.get('/switch/{switch}')
def inspect_switch(switch: str, topology_instance_id: str = Query(..., max_length=240),
                   graph_version: str = Query(..., max_length=240)):
    network = live_api.network
    with network.lock:
        snapshot = network.snapshot()
        if not snapshot.get('ready') or snapshot.get('topology_instance_id') != topology_instance_id or snapshot.get('graph_version') != graph_version:
            raise HTTPException(409, 'La sesion o el estado de red cambio; vuelve a seleccionar el elemento.')
        try:
            return reader.read(network, snapshot, switch)
        except ValueError as error:
            raise HTTPException(422, str(error))
