import { useState } from "react";
import { mostrarValor, type Registro } from "./api";
import Paginador, { FILAS_POR_PAGINA } from "./Paginador";
import DetalleRegistro, { etiqueta } from "./DetalleRegistro";

type Coleccion = { titulo: string; filas: Registro[]; es_muestra: boolean };
const normalizar = (valor: string) => valor.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
const campoSimple = (valor: unknown) => valor == null || ["string", "number", "boolean"].includes(typeof valor);

export default function TablaDatos({ datos }: { datos: Registro }) {
  const [indice, setIndice] = useState(0);
  const [pagina, setPagina] = useState(0);
  const [busqueda, setBusqueda] = useState("");
  const [estado, setEstado] = useState("");
  const [nivel, setNivel] = useState("");
  const [detalle, setDetalle] = useState<Registro | null>(null);
  let colecciones = (Array.isArray(datos.colecciones) ? datos.colecciones : []).filter((c): c is Coleccion =>
    !!c && typeof c === "object" && typeof c.titulo === "string" && Array.isArray(c.filas),
  );
  if (!colecciones.length && Array.isArray(datos.resultados_muestra)) {
    const filas = datos.resultados_muestra.filter((f): f is Registro => !!f && typeof f === "object" && !Array.isArray(f));
    if (filas.length) colecciones = [{ titulo: "Registros disponibles en esta respuesta", filas, es_muestra: true }];
  }
  const coleccion = colecciones[indice];
  if (!coleccion) return null;
  const filas = coleccion.filas.filter((fila) => (!estado || fila.estado === estado) && (!nivel || fila.nivel === nivel) && Object.values(fila).some((valor) =>
    campoSimple(valor) && normalizar(String(valor ?? "")).includes(normalizar(busqueda.trim())),
  ));
  const claves = [...new Set(coleccion.filas.flatMap((fila) => Object.keys(fila).filter((k) => campoSimple(fila[k]))))];
  const principales = ["nombre_establecimiento", "codigo_establecimiento", "titulo", "titulo_obtenido", "nombre_institucion", "institucion", "municipio", "departamento", "tipo", "linea_o_modalidad", "categoria", "valor", "cantidad", "conteo", "descripcion", "anio", "a_o"];
  const esOferta = coleccion.titulo === "Oferta de educación superior";
  const columnas = esOferta ? ["titulo_obtenido", "programa", "institucion", "nivel", "estado"].filter(c => claves.includes(c))
    : [...principales.filter((c) => claves.includes(c)), ...claves.filter((c) => !principales.includes(c))].slice(0, 3);
  const desde = pagina * FILAS_POR_PAGINA;
  return <section className="directorio tabla-datos" aria-labelledby="datos-titulo">
    <h3 id="datos-titulo">Explora los datos</h3>
    {colecciones.length > 1 && <label className="buscar-colegio">Información para explorar
      <select aria-label="Información para explorar" value={indice} onChange={(e) => { setIndice(Number(e.target.value)); setPagina(0); setBusqueda(""); setEstado(""); setNivel(""); }}>
        {colecciones.map((c, i) => <option value={i} key={i}>{c.titulo}</option>)}
      </select>
    </label>}
    <p className="directorio-vigencia">{coleccion.titulo}</p>
    <p className="ayuda-listado">{coleccion.es_muestra
      ? "Estos registros son una muestra o un resumen de la respuesta, no el total de la fuente."
      : "Coincidencias de la búsqueda según la fuente consultada."} Pulsa un registro para ver su detalle.</p>
    {esOferta && <div className="filtros-oferta">
      {([["estado", "Estado", estado, setEstado], ["nivel", "Nivel académico", nivel, setNivel]] as const).map(([clave, label, valor, cambiar]) =>
        <label key={clave} className="buscar-colegio">{label}<select aria-label={label} value={valor} onChange={(e) => { cambiar(e.target.value); setPagina(0); }}>
          <option value="">Todos</option>
          {[...new Set(coleccion.filas.map(fila => fila[clave]).filter((v): v is string => typeof v === "string"))].sort().map(opcion => <option value={opcion} key={opcion}>{opcion}</option>)}
        </select></label>,
      )}
    </div>}
    <label className="buscar-colegio">Buscar en estos datos
      <input type="search" value={busqueda} onChange={(e) => { setBusqueda(e.target.value); setPagina(0); }} />
    </label>
    <p className="resumen-lista" role="status">{filas.length ? `Mostrando ${desde + 1}–${Math.min(desde + FILAS_POR_PAGINA, filas.length)} de ${filas.length} registros disponibles` : "No hay registros que coincidan con la búsqueda."}</p>
    <div className="panel-registros">
      <table aria-label={coleccion.titulo}>
        <thead><tr>{columnas.map((c) => <th scope="col" key={c}><span className="celda-datos">{etiqueta(c)}</span></th>)}</tr></thead>
        <tbody>{filas.slice(desde, desde + FILAS_POR_PAGINA).map((fila, i) => <tr key={desde + i}>
          {columnas.map((c, j) => <td key={c}>{j === 0
            ? <button type="button" className="nombre-colegio" aria-label={`Ver detalle del registro ${desde + i + 1}`} onClick={() => setDetalle(fila)}>{mostrarValor(fila[c], c)}</button>
            : <span className="celda-datos">{/codigo|cod_dane/.test(c) ? String(fila[c] ?? "No disponible") : mostrarValor(fila[c], c)}</span>}</td>)}
        </tr>)}</tbody>
      </table>
    </div>
    <Paginador pagina={pagina} total={filas.length} cambiar={setPagina} />
    {detalle && <DetalleRegistro fila={detalle} cerrar={() => setDetalle(null)} titulo={coleccion.titulo === "Colegios y códigos DANE" ? "Código DANE del colegio" : "Detalle del registro"} />}
  </section>;
}
