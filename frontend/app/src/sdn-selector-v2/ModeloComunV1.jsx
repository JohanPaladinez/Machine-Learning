
import { useEffect, useState } from "react";
import { BrainCircuit } from "lucide-react";

export default function ModeloComunV1({ apiUrl, info = false }) {
  const base = String(apiUrl || "").trim().replace(/\/+$/, "");
  const [estado, setEstado] = useState(null);

  useEffect(() => {
    let activo = true;
    let controlador;
    let limite;

    async function actualizar() {
      controlador = new AbortController();
      limite = setTimeout(() => controlador.abort(), 7000);
      try {
        const respuesta = await fetch(`${base}/api/sdn/ml/estado`, {
          cache: "no-store",
          signal: controlador.signal,
        });
        const datos = await respuesta.json();
        if (!respuesta.ok) {
          throw new Error(
            typeof datos.detail === "string"
              ? datos.detail
              : "No se pudo consultar el modelo."
          );
        }
        if (datos.estado !== "disponible") {
          throw new Error("El modelo no confirma disponibilidad.");
        }
        if (activo) setEstado(datos);
      } catch (error) {
        if (activo) setEstado({
          estado: "sin_conexion",
          mensaje: error.name === "AbortError"
            ? "El servicio del modelo no respondio a tiempo."
            : error.message,
        });
      } finally {
        clearTimeout(limite);
      }
    }

    setEstado(null);
    actualizar();
    const intervalo = setInterval(actualizar, 15000);
    return () => {
      activo = false;
      clearInterval(intervalo);
      clearTimeout(limite);
      controlador?.abort();
    };
  }, [base]);

  const disponible = estado?.estado === "disponible";
  const etiqueta = !estado
    ? "Comprobando"
    : disponible ? "Cargado" : "Sin conexión";

  if (info) {
    return (
      <div className="sdn-pending-note" style={disponible ? {
        borderColor: "rgba(52,211,153,.3)",
        background: "rgba(52,211,153,.06)",
      } : undefined}>
        <BrainCircuit size={18} />
        <div>
          <strong>Modelo común ML: {etiqueta.toLowerCase()}</strong>
          <p>
            {disponible
              ? "Modelo conectado y evaluación de test completada. Selecciona un enlace para consultar su predicción cuando tenga mediciones recientes completas."
              : estado?.mensaje || "Consultando el servicio del modelo en RYU."}
          </p>
        </div>
      </div>
    );
  }

  return (
    <article className="stat-card">
      <div className="stat-top">
        <span>Modelo común ML</span><BrainCircuit size={19} />
      </div>
      <div className="stat-value status-value" style={{
        color: disponible ? "#34d399" : "#fbbf24",
      }}>{etiqueta}</div>
      <div className="stat-description">
        {disponible
          ? "Modelo entrenado y evaluado para ambas topologías"
          : "Conexión con el servicio ML de RYU"}
      </div>
    </article>
  );
}
