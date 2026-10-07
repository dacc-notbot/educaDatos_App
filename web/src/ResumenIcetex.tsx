import { useState } from "react";
import { mostrarValor, type Registro } from "./api";
import Paginador, { FILAS_POR_PAGINA } from "./Paginador";
import DetalleRegistro from "./DetalleRegistro";

type Fila = { categoria: string; cantidad: number };
type Distribucion = { clave: string; titulo: string; nota: string; filas: Fila[]; permite_grafico: boolean };
type Estadisticas = { unidad: string; explicacion: string; territorio: string; anio: number | null; total: number | null;
  cobertura_disponible: boolean; dimension_preferida?: string; serie_anual: { anio: number; cantidad: number }[]; distribuciones: Distribucion[] };

function VistaIcetex({ detalle, buscar, pregunta }: { detalle: Registro; pregunta: string; buscar: (pregunta: string) => void }) {
  const estadisticas = detalle.visualizacion_icetex as Estadisticas;
  const [dimension, setDimension] = useState(estadisticas?.dimension_preferida || "nivel_de_formacion");
  const [modo, setModo] = useState("grafico");
  const [pagina, setPagina] = useState(0);
  const [registro, setRegistro] = useState<Registro | null>(null);
  if (!estadisticas?.cobertura_disponible) return null;
  const basePregunta = pregunta.replace(/\b(?:19|20)\d{2}\b/g, "");
  const cambiarTipo = (tipo: string) => buscar(basePregunta.replace(/renov[a-záéíóú]*|otorg[a-záéíóú]*/gi, "") + ` ${tipo}${estadisticas.anio ? ` en ${estadisticas.anio}` : ""}`);
  const anual = dimension === "serie_anual";
  const distribucion = estadisticas.distribuciones.find(d => d.clave === dimension);
  const titulo = anual ? "Evolución por año" : distribucion?.titulo || "Distribución";
  const filas: Fila[] = anual ? estadisticas.serie_anual.map(f => ({ categoria: String(f.anio), cantidad: f.cantidad })) : distribucion?.filas || [];
  const desde = pagina * FILAS_POR_PAGINA;
  const legible = (texto: string) => ({ "N/A": "Sin información (N/A)", "OFICIAL": "Público", "PRIVADO": "Privado", "MATRICULA": "Matrícula", "SOSTENIMIENTO": "Sostenimiento", "PREGRADO": "Pregrado", "POSGRADO PAÍS": "Posgrado en Colombia", "CRÉDITO EXTERIOR": "Estudios en el exterior" } as Record<string, string>)[texto] || texto;
  const visibles = filas.map(f => ({ ...f, categoria: legible(f.categoria) })).slice(desde, desde + FILAS_POR_PAGINA);
  const maximo = Math.max(1, ...filas.map(f => f.cantidad));
  const grafico = modo === "grafico" && (anual || distribucion?.permite_grafico);
  const porcentaje = (cantidad: number) => estadisticas.total && !anual ? new Intl.NumberFormat("es-CO", { maximumFractionDigits: 1 }).format(cantidad / estadisticas.total * 100) + " %" : "—";
  return <section className="directorio icetex-resumen" aria-labelledby="icetex-titulo">
    <h3 id="icetex-titulo">ICETEX en cifras</h3>
    <dl className="indicadores">
      <div><dt>{estadisticas.unidad}</dt><dd>{mostrarValor(estadisticas.total)}</dd></div>
      <div><dt>Año consultado</dt><dd>{mostrarValor(estadisticas.anio, "anio")}</dd></div>
      <div><dt>Departamento de origen</dt><dd>{estadisticas.territorio}</dd></div>
    </dl>
    <p>{estadisticas.explicacion}</p>
    <p className="ayuda-listado">La fuente permite consultar departamentos de origen. No identifica ciudades ni universidades por nombre. Los códigos de desembolso no son valores exactos en pesos. El último año publicado puede actualizarse y no garantiza un reporte anual completo. Cada vista describe el mismo total; no se suman las vistas entre sí.</p>
    <div className="filtros-oferta">
      <label className="buscar-colegio">Tipo de datos de ICETEX
        <select aria-label="Tipo de datos de ICETEX" value={String(detalle.tipo_credito)} onChange={e => cambiarTipo(e.target.value)}>
          <option value="otorgados">Nuevos beneficiarios</option><option value="renovados">Renovaciones</option>
        </select>
      </label>
      <label className="buscar-colegio">Año de ICETEX
        <select aria-label="Año de ICETEX" value={estadisticas.anio ?? ""} onChange={e => buscar(`${basePregunta} en ${e.target.value}`)}>
          {estadisticas.anio && !estadisticas.serie_anual.some(f => f.anio === estadisticas.anio) && <option value={estadisticas.anio}>{estadisticas.anio} (sin datos)</option>}
          {!estadisticas.anio && <option value="">Sin datos</option>}
          {estadisticas.serie_anual.map(f => <option key={f.anio} value={f.anio}>{f.anio}</option>)}
        </select>
      </label>
      <label className="buscar-colegio">Ver cifras por
        <select aria-label="Ver cifras por" value={dimension} onChange={e => { setDimension(e.target.value); setPagina(0); }}>
          {estadisticas.distribuciones.map(d => <option key={d.clave} value={d.clave}>{d.titulo}</option>)}
          <option value="serie_anual">Evolución por año</option>
        </select>
      </label>
    </div>
    <p className="directorio-vigencia">{titulo}</p>
    <p className="ayuda-listado" id="icetex-nota">{anual
      ? "Cada barra representa un año disponible en la fuente. Compara las cantidades reportadas; no es un seguimiento de las mismas personas."
      : distribucion?.nota} {anual ? "" : "Las cantidades suman el total del año consultado."}</p>
    <div className="filtros-colegios" aria-label="Presentación de ICETEX">
      <button type="button" aria-pressed={!grafico} onClick={() => setModo("tabla")}>Tabla</button>
      {(anual || distribucion?.permite_grafico) && <button type="button" aria-pressed={!!grafico} onClick={() => setModo("grafico")}>Gráfico</button>}
    </div>
    <p className="resumen-lista" role="status">{filas.length ? `Mostrando ${desde + 1}–${Math.min(desde + FILAS_POR_PAGINA, filas.length)} de ${filas.length} categorías` : "No hay datos para el año consultado. Puedes elegir otro año disponible."}</p>
    <div className="panel-registros">
      {grafico ? <div className="grafico-icetex" role="img" aria-label={`${titulo}. ${visibles.map(f => `${f.categoria}: ${mostrarValor(f.cantidad)} ${estadisticas.unidad.toLowerCase()}`).join("; ")}`} aria-describedby="icetex-nota">
        <p className="unidad-grafico" aria-hidden="true">{estadisticas.unidad}</p>
        {visibles.map(f => <div className="fila-grafico" key={f.categoria} aria-hidden="true">
          <span className="nombre-categoria" title={f.categoria}>{f.categoria}</span>
          <div className="barra-fondo"><span style={{ width: `${f.cantidad / maximo * 100}%` }} /></div>
          <strong>{mostrarValor(f.cantidad)}</strong>
        </div>)}
      </div> : <table aria-label={`ICETEX: ${titulo}`}>
        <thead><tr><th scope="col">{anual ? "Año" : titulo}</th><th scope="col">Cantidad</th>{!anual && <th scope="col">Del total</th>}</tr></thead>
        <tbody>{visibles.map(f => <tr key={f.categoria}><td><button type="button" className="nombre-colegio" onClick={() => setRegistro({ categoria: f.categoria, cantidad: f.cantidad, unidad: estadisticas.unidad, ...(anual ? { anio: Number(f.categoria) } : { anio: estadisticas.anio, participacion: porcentaje(f.cantidad) }) })}>{f.categoria}</button></td>
          <td>{mostrarValor(f.cantidad)}</td>{!anual && <td>{porcentaje(f.cantidad)}</td>}</tr>)}
        </tbody>
      </table>}
    </div>
    <Paginador pagina={pagina} total={filas.length} cambiar={setPagina} nombre="categorías de ICETEX" />
    {registro && <DetalleRegistro fila={registro} cerrar={() => setRegistro(null)} titulo="Detalle de la cifra de ICETEX" />}
  </section>;
}

export default function ResumenIcetex({ detalle, buscar, pregunta }: { detalle: Registro; pregunta: string; buscar: (pregunta: string) => void }) {
  const [indice, setIndice] = useState(0);
  const comparacion = Array.isArray(detalle.comparacion_icetex) ? detalle.comparacion_icetex as Registro[] : [];
  if (!comparacion.length) return <VistaIcetex detalle={detalle} buscar={buscar} pregunta={pregunta} />;
  const seleccionado = comparacion[indice];
  const visual = seleccionado.visualizacion_icetex as Estadisticas;
  return <div>
    <label className="buscar-colegio">Datos que quieres comparar
      <select aria-label="Datos que quieres comparar" value={indice} onChange={e => setIndice(Number(e.target.value))}>
        {comparacion.map((d, i) => <option key={i} value={i}>{String((d.visualizacion_icetex as Estadisticas).unidad)}</option>)}
      </select>
    </label>
    <p className="ayuda-listado">Nuevos beneficiarios y renovaciones son medidas distintas. No se suman ni equivalen a personas únicas.</p>
    <VistaIcetex key={indice} detalle={seleccionado} buscar={buscar} pregunta={pregunta.replace(/renov[a-záéíóú]*|otorg[a-záéíóú]*|\bnuevos?\b/gi, "") + ` ICETEX ${seleccionado.tipo_credito} en ${visual.territorio}${visual.anio ? ` en ${visual.anio}` : ""}`} />
  </div>;
}
