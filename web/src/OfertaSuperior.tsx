import { useState, type FormEvent } from "react";
import { mostrarValor, type Registro } from "./api";

export default function OfertaSuperior({ detalle, buscar }: { detalle: Registro; buscar: (pregunta: string) => void }) {
  const [nombre, setNombre] = useState("");
  const [ambito, setAmbito] = useState("territorio");
  const territorio = detalle.territorio as Registro | undefined;
  const lugar = String(territorio?.municipio || territorio?.departamento || "Colombia");
  const distribuciones = [["distribucion_estado", "Estado reportado"], ["distribucion_nivel", "Nivel académico"]];
  function enviar(e: FormEvent) {
    e.preventDefault();
    if (nombre.trim()) buscar(`Programa "${nombre.trim()}" en ${ambito === "nacional" ? "Colombia" : lugar}`);
  }
  return <section className="oferta-superior" aria-label="Oferta de educación superior">
    {detalle.identificacion_programas_confiable === false && <p className="ayuda-listado">La búsqueda usa los títulos otorgados que informa el MEN; esta fuente no permite identificar de forma fiable cada programa.</p>}
    <div className="distribuciones-oferta">
      {distribuciones.map(([clave, titulo]) => {
        const filas = Array.isArray(detalle[clave]) ? (detalle[clave] as Registro[]) : [];
        return filas.length ? <div key={clave}><h3>{titulo}</h3><dl>{filas.map((fila, i) =>
          <div key={i}><dt>{String(fila.valor)}</dt><dd>{mostrarValor(fila.conteo)}</dd></div>,
        )}</dl></div> : null;
      })}
    </div>
    <p className="ayuda-listado">Las cantidades corresponden a registros de oferta publicados; pueden incluir el mismo título en diferentes instituciones, niveles o sedes.</p>
    <form className="busqueda-programa" onSubmit={enviar}>
      <label className="buscar-colegio">¿Qué programa o título buscas?
        <input value={nombre} maxLength={200} placeholder="Por ejemplo, Ingeniería de Sistemas" onChange={(e) => setNombre(e.target.value)} />
      </label>
      <label className="buscar-colegio">Dónde buscar
        <select aria-label="Dónde buscar" value={ambito} onChange={(e) => setAmbito(e.target.value)}>
          <option value="territorio">{lugar}</option>
          {lugar !== "Colombia" && <option value="nacional">Toda Colombia</option>}
        </select>
      </label>
      <button className="boton-consultar" type="submit" disabled={!nombre.trim()}>Buscar programa</button>
    </form>
  </section>;
}
