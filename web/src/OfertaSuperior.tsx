import { useState, type FormEvent } from "react";
import { mostrarValor, type Registro } from "./api";
import SelectorTerritorio from "./SelectorTerritorio";
import Paginador, { FILAS_POR_PAGINA } from "./Paginador";

type Grupo = { nivel?: string; modalidad?: string; ciclo?: string; total: number; activos: number; inactivos: number; sin_estado: number };
type Resumen = { total_ofertas: number; unidad_conteo: string; por_estado: { estado: string; total: number }[]; por_nivel: Grupo[]; por_modalidad: Grupo[]; por_ciclo: Grupo[] };

export default function OfertaSuperior({ detalle, buscar }: { detalle: Registro; buscar: (pregunta: string, parametros?: Registro) => void }) {
  const [nombre, setNombre] = useState("");
  const original = detalle.territorio as Registro | undefined;
  const [territorio, setTerritorio] = useState<{ departamento?: string; municipio?: string }>({
    departamento: typeof original?.departamento === "string" ? original.departamento : undefined,
    municipio: typeof original?.municipio === "string" ? original.municipio : undefined,
  });
  const [valido, setValido] = useState(true);
  const [vista, setVista] = useState("nivel");
  const [pagina, setPagina] = useState(0);
  const resumen = detalle.resumen_oferta as Resumen | undefined;
  const procedencia = detalle.procedencia_oferta as Registro | undefined;
  const grupos = resumen ? (vista === "nivel" ? resumen.por_nivel : vista === "modalidad" ? resumen.por_modalidad : resumen.por_ciclo) : [];
  const clave = vista === "nivel" ? "nivel" : vista === "modalidad" ? "modalidad" : "ciclo";
  function enviar(e: FormEvent) {
    e.preventDefault();
    if (!valido) return;
    const lugar = territorio.municipio ? `${territorio.municipio} (${territorio.departamento})` : territorio.departamento || "Colombia";
    buscar(nombre.trim() ? `Programa «${nombre.trim()}» en ${lugar}` : `Oferta de educación superior en ${lugar}`, {
      ...(nombre.trim() ? { texto: nombre.trim() } : {}), ...territorio,
    });
  }
  return <section className="oferta-superior" aria-label="Resumen de educación superior">
    <div className="procedencia-oferta">
      <span className="procedencia-icono" aria-hidden="true">✓</span>
      <p>{typeof procedencia?.descripcion_ciudadana === "string" ? procedencia.descripcion_ciudadana : "Información del Ministerio de Educación Nacional publicada en Datos Abiertos del Gobierno de Colombia. La fuente no informa el año de registro."}</p>
    </div>
    {resumen && <>
      <div className="oferta-cifras" aria-label="Estado de la oferta reportada">
        <div className="oferta-total"><span>{resumen.unidad_conteo === "programas" ? "Programas reportados" : "Ofertas reportadas"}</span><strong>{mostrarValor(resumen.total_ofertas)}</strong></div>
        {resumen.por_estado.map(grupo => <div key={grupo.estado} className={grupo.estado === "Activo" ? "oferta-activa" : "oferta-inactiva"}>
          <span>{grupo.estado === "Activo" ? "Activas" : grupo.estado === "Inactivo" ? "Inactivas" : grupo.estado}</span><strong>{mostrarValor(grupo.total)}</strong>
        </div>)}
      </div>
      <div className="oferta-distribucion">
        <div className="oferta-distribucion-cabecera"><h3>Conoce la oferta</h3><p>Compara el total con su estado reportado.</p></div>
        <div className="oferta-vistas" role="group" aria-label="Resumen de la oferta">
          {[["nivel", "Nivel académico"], ["modalidad", "Modalidad"], ["ciclo", "Pregrado y posgrado"]].map(([valor, etiqueta]) => <button type="button" key={valor} aria-pressed={vista === valor} onClick={() => { setVista(valor); setPagina(0); }}>{etiqueta}</button>)}
        </div>
        <div className="resumen-oferta-panel">
          <table aria-label={`Oferta por ${vista}`}>
            <thead><tr><th scope="col">{vista === "nivel" ? "Nivel académico" : vista === "modalidad" ? "Modalidad" : "Formación"}</th><th scope="col">Total</th><th scope="col">Activas</th><th scope="col">Inactivas</th></tr></thead>
            <tbody>{grupos.slice(pagina * FILAS_POR_PAGINA, (pagina + 1) * FILAS_POR_PAGINA).map(grupo => <tr key={grupo[clave]}><th scope="row">{grupo[clave] || "Sin información"}</th><td>{mostrarValor(grupo.total)}</td><td className="cantidad-activa">{mostrarValor(grupo.activos)}</td><td>{mostrarValor(grupo.inactivos)}</td></tr>)}</tbody>
          </table>
        </div>
        <Paginador pagina={pagina} total={grupos.length} cambiar={setPagina} nombre="resumen de oferta" />
        {grupos.some(g => g.sin_estado > 0) && <p className="ayuda-listado">El total incluye {mostrarValor(grupos.reduce((s, g) => s + g.sin_estado, 0))} ofertas cuyo estado no está informado como activo o inactivo.</p>}
        <p className="ayuda-listado">Las cifras describen la oferta encontrada para tu búsqueda. Un título puede aparecer en distintas instituciones, modalidades o lugares.</p>
      </div>
    </>}
    <form className="busqueda-programa nueva-busqueda-programa" onSubmit={enviar}>
      <div className="busqueda-titulo"><span className="eyebrow">CAMBIA TU BÚSQUEDA</span><h3>Un programa, otro lugar, más posibilidades</h3></div>
      <label className="buscar-colegio">¿Qué programa o título buscas?
        <input value={nombre} maxLength={200} placeholder="Ejemplo: Ingeniería de Sistemas; déjalo vacío para ver toda la oferta" onChange={e => setNombre(e.target.value)} />
      </label>
      <SelectorTerritorio valor={territorio} onChange={setTerritorio} onValidezChange={setValido} />
      <div className="oferta-enviar"><p className="ayuda-listado">Puedes buscar un nombre o explorar la oferta de un departamento, municipio o toda Colombia.</p><button className="boton-consultar" type="submit" disabled={!valido}>Explorar oferta <svg className="superior-icono" aria-hidden="true" viewBox="0 0 16 16" fill="none"><path d="M4 12 12 4M4 4h8v8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg></button></div>
    </form>
  </section>;
}
