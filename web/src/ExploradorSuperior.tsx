import { useId, useRef, useState } from "react";
import type { Registro } from "./api";
import DetalleRegistro from "./DetalleRegistro";
import Paginador, { FILAS_POR_PAGINA } from "./Paginador";
import "./ExploradorSuperior.css";

type Vista = "oferta" | "instituciones" | "modalidades" | "niveles" | "formacion";
type Grupo = { nombre: string; total: number; activos: number; inactivos: number; sinEstado: number };
const VISTAS: { id: Vista; titulo: string }[] = [
  { id: "oferta", titulo: "Programas y títulos" },
  { id: "instituciones", titulo: "Instituciones" },
  { id: "modalidades", titulo: "Modalidades" },
  { id: "niveles", titulo: "Niveles" },
  { id: "formacion", titulo: "Formación" },
];
const normalizar = (valor: string) => valor.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
const texto = (valor: unknown, defecto = "No informado") => typeof valor === "string" && valor.trim() ? valor.trim() : defecto;
const numero = (valor: unknown) => typeof valor === "number" && Number.isFinite(valor) && valor >= 0 ? valor : 0;
const registros = (valor: unknown): Registro[] => Array.isArray(valor)
  ? valor.filter((fila): fila is Registro => !!fila && typeof fila === "object" && !Array.isArray(fila)) : [];
const tituloOferta = (fila: Registro) => texto(fila.programa, texto(fila.titulo_obtenido, "Título no informado"));
const modalidadOferta = (fila: Registro) => texto(fila.modalidad, texto(fila.metodologia_modalidad));
const cicloOferta = (fila: Registro) => {
  const nivel = normalizar(texto(fila.nivel));
  if (/especializa/.test(nivel)) return "Especialización";
  if (/maestr/.test(nivel)) return "Maestría";
  if (/doctor/.test(nivel)) return "Doctorado";
  if (normalizar(texto(fila.ciclo)) === "posgrado") return "Posgrado";
  if (normalizar(texto(fila.ciclo)) === "pregrado") return "Pregrado";
  if (/universitaria|tecnologica|tecnica profesional/.test(nivel)) return "Pregrado";
  return "Formación no informada";
};
const cicloFuente = (fila: Registro) => {
  const publicado = normalizar(texto(fila.ciclo));
  if (publicado === "pregrado") return "Pregrado";
  if (publicado === "posgrado") return "Posgrado";
  const grupo = cicloOferta(fila);
  if (["Especialización", "Maestría", "Doctorado", "Posgrado"].includes(grupo)) return "Posgrado";
  return grupo === "Pregrado" ? "Pregrado" : "Formación no informada";
};
const contarGrupos = (filas: Registro[], clave: string): Grupo[] => {
  const grupos = new Map<string, Grupo>();
  for (const fila of filas) {
    const nombre = clave === "metodologia_modalidad" ? modalidadOferta(fila) : texto(fila[clave]);
    const grupo = grupos.get(nombre) || { nombre, total: 0, activos: 0, inactivos: 0, sinEstado: 0 };
    grupo.total += 1;
    const estado = normalizar(texto(fila.estado));
    if (estado === "activo") grupo.activos += 1;
    else if (estado === "inactivo") grupo.inactivos += 1;
    else grupo.sinEstado += 1;
    grupos.set(nombre, grupo);
  }
  return [...grupos.values()].sort((a, b) => b.total - a.total || a.nombre.localeCompare(b.nombre, "es"));
};
const leerGrupos = (valor: unknown, clave: string, totalClave = "total"): Grupo[] => registros(valor).map(fila => ({
  nombre: clave === "ciclo" && /^(sin informacion|no informado|no disponible)$/.test(normalizar(texto(fila[clave])))
    ? "Formación no informada" : texto(fila[clave]), total: numero(fila[totalClave]), activos: numero(fila.activos),
  inactivos: numero(fila.inactivos), sinEstado: numero(fila.sin_estado),
}));
const formato = (valor: number) => valor.toLocaleString("es-CO");
const Flecha = ({ diagonal = false }: { diagonal?: boolean }) => <svg className="superior-icono" aria-hidden="true" viewBox="0 0 16 16" fill="none"><path d={diagonal ? "M4 12 12 4M4 4h8v8" : "M2 8h12M8 2l6 6-6 6"} stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>;

export default function ExploradorSuperior({ detalle }: { detalle: Registro }) {
  const id = useId();
  const pestanas = useRef<(HTMLButtonElement | null)[]>([]);
  const [vista, setVista] = useState<Vista>("oferta");
  const [pagina, setPagina] = useState(0);
  const [busqueda, setBusqueda] = useState("");
  const [institucion, setInstitucion] = useState("");
  const [estado, setEstado] = useState("");
  const [modalidad, setModalidad] = useState("");
  const [nivel, setNivel] = useState("");
  const [ciclo, setCiclo] = useState("");
  const [filaDetalle, setFilaDetalle] = useState<Registro | null>(null);
  const ofertas = registros(detalle.lista_oferta);
  const resumen = detalle.resumen_oferta && typeof detalle.resumen_oferta === "object"
    ? detalle.resumen_oferta as Registro : {};
  const unidad = resumen.unidad_conteo === "programas" ? "programas" : "ofertas publicadas";
  const instituciones = leerGrupos(resumen.instituciones, "institucion", "total_ofertas");
  const modalidades = leerGrupos(resumen.por_modalidad, "modalidad");
  const niveles = leerGrupos(resumen.por_nivel, "nivel");
  const ciclos = leerGrupos(resumen.por_ciclo, "ciclo");
  const resumenInstitucion = registros(resumen.instituciones).find(fila => fila.institucion === institucion);
  const ofertaInstitucion = ofertas.filter(fila => texto(fila.institucion) === institucion);
  const modalidadesInstitucion = leerGrupos(resumenInstitucion?.modalidades, "modalidad");
  const nivelesInstitucion = leerGrupos(resumenInstitucion?.niveles, "nivel");
  const ciclosInstitucion = leerGrupos(resumenInstitucion?.ciclos, "ciclo");
  const agrupaciones = {
    instituciones: instituciones.length ? instituciones : contarGrupos(ofertas, "institucion"),
    modalidades: institucion ? (modalidadesInstitucion.length ? modalidadesInstitucion : contarGrupos(ofertaInstitucion, "metodologia_modalidad"))
      : modalidades.length ? modalidades : contarGrupos(ofertas, "metodologia_modalidad"),
    niveles: institucion ? (nivelesInstitucion.length ? nivelesInstitucion : contarGrupos(ofertaInstitucion, "nivel"))
      : niveles.length ? niveles : contarGrupos(ofertas, "nivel"),
    formacion: institucion ? (ciclosInstitucion.length ? ciclosInstitucion : contarGrupos(ofertaInstitucion.map(fila => ({ ...fila, ciclo: cicloFuente(fila) })), "ciclo"))
      : ciclos.length ? ciclos : contarGrupos(ofertas.map(fila => ({ ...fila, ciclo: cicloFuente(fila) })), "ciclo"),
  };
  const opcionesLocales = institucion ? ofertaInstitucion : ofertas;
  const opciones = (clave: string) => [...new Set(opcionesLocales.map(fila => clave === "metodologia_modalidad" ? modalidadOferta(fila) : texto(fila[clave])))].sort((a, b) => a.localeCompare(b, "es"));
  const gruposCiclo = [...new Set(opcionesLocales.flatMap(fila => [cicloOferta(fila), cicloFuente(fila)]))].sort((a, b) => a.localeCompare(b, "es"));
  const busquedaNormalizada = normalizar(busqueda.trim());
  const filtradas = ofertas.filter(fila => (!institucion || texto(fila.institucion) === institucion)
    && (!estado || texto(fila.estado) === estado)
    && (!modalidad || modalidadOferta(fila) === modalidad)
    && (!nivel || texto(fila.nivel) === nivel)
    && (!ciclo || cicloOferta(fila) === ciclo || cicloFuente(fila) === ciclo)
    && [tituloOferta(fila), texto(fila.institucion), texto(fila.municipio), texto(fila.departamento)]
      .some(valor => normalizar(valor).includes(busquedaNormalizada)));
  const grupos = vista === "oferta" ? [] : agrupaciones[vista].filter(grupo => normalizar(grupo.nombre).includes(busquedaNormalizada));
  const total = vista === "oferta" ? filtradas.length : grupos.length;
  const paginaValida = Math.min(pagina, Math.max(0, Math.ceil(total / FILAS_POR_PAGINA) - 1));
  const desde = paginaValida * FILAS_POR_PAGINA;
  const seleccion = agrupaciones.instituciones.find(grupo => grupo.nombre === institucion);
  const cambiarVista = (nueva: Vista) => { setVista(nueva); setPagina(0); setBusqueda(""); };
  const restablecerFiltros = () => { setInstitucion(""); setEstado(""); setModalidad(""); setNivel(""); setCiclo(""); setBusqueda(""); setPagina(0); };
  const verOferta = (grupo: Grupo) => {
    const institucionAnterior = institucion;
    restablecerFiltros();
    if (vista === "instituciones") setInstitucion(grupo.nombre);
    else {
      setInstitucion(institucionAnterior);
      if (vista === "modalidades") setModalidad(grupo.nombre);
      else if (vista === "niveles") setNivel(grupo.nombre);
      else if (vista === "formacion") setCiclo(grupo.nombre);
    }
    setVista("oferta");
    pestanas.current[0]?.focus();
  };
  const filtro = (etiqueta: string, valor: string, opcionesFiltro: string[], cambiar: (valor: string) => void, todos: string) =>
    <label className="superior-filtro">{etiqueta}<select aria-label={etiqueta} value={valor} onChange={event => { cambiar(event.target.value); setPagina(0); }}>
      <option value="">{todos}</option>{opcionesFiltro.map(opcion => <option key={opcion} value={opcion}>{opcion}</option>)}
    </select></label>;

  return <section className="superior-explorador" aria-labelledby={`${id}-titulo`}>
    <header className="superior-cabecera">
      <div><span className="superior-eyebrow">Educación superior · a tu medida</span><h3 id={`${id}-titulo`}>Explora los datos <span><Flecha diagonal /></span></h3>
        <p>Elige qué quieres conocer. Filtra los resultados o abre una oferta para ver sus datos.</p></div>
      <span className="superior-total">{formato(numero(resumen.total_ofertas) || ofertas.length)}<small>{unidad}</small></span>
    </header>
    <div className="superior-pestanas" role="tablist" aria-label="Explorar educación superior">
      {VISTAS.map((item, indice) => <button key={item.id} type="button" role="tab" id={`${id}-tab-${item.id}`}
        aria-controls={`${id}-panel`} aria-selected={vista === item.id} tabIndex={vista === item.id ? 0 : -1}
        ref={elemento => { pestanas.current[indice] = elemento; }} onClick={() => cambiarVista(item.id)} onKeyDown={evento => {
          let siguiente = indice;
          if (evento.key === "ArrowRight") siguiente = (indice + 1) % VISTAS.length;
          else if (evento.key === "ArrowLeft") siguiente = (indice - 1 + VISTAS.length) % VISTAS.length;
          else if (evento.key === "Home") siguiente = 0;
          else if (evento.key === "End") siguiente = VISTAS.length - 1;
          else return;
          evento.preventDefault(); cambiarVista(VISTAS[siguiente].id); pestanas.current[siguiente]?.focus();
        }}>{item.titulo}</button>)}
    </div>
    <div id={`${id}-panel`} role="tabpanel" aria-labelledby={`${id}-tab-${vista}`} tabIndex={0}>
      {seleccion && vista !== "instituciones" && <div className="superior-seleccion"><div><strong>{seleccion.nombre}</strong><span>En esta consulta: {formato(seleccion.total)} {unidad} · {formato(seleccion.activos)} activas · {formato(seleccion.inactivos)} inactivas{seleccion.sinEstado > 0 ? ` · ${formato(seleccion.sinEstado)} sin estado informado` : ""}</span></div>
        <button type="button" onClick={restablecerFiltros}>Ver todas las instituciones</button></div>}
      {vista === "oferta" ? <>
        <div className="superior-filtros">
          {filtro("Estado de la oferta", estado, opciones("estado"), setEstado, "Todos los estados")}
          {filtro("Modalidad del programa", modalidad, opciones("metodologia_modalidad"), setModalidad, "Todas las modalidades")}
          {filtro("Nivel académico de la oferta", nivel, opciones("nivel"), setNivel, "Todos los niveles")}
          {filtro("Grupo de formación", ciclo, gruposCiclo, setCiclo, "Toda la formación")}
        </div>
        {!seleccion && filtro("Institución de la oferta", institucion, opciones("institucion"), valor => {
          setInstitucion(valor); setEstado(""); setModalidad(""); setNivel(""); setCiclo("");
        }, "Todas las instituciones")}
      </> : <p className="superior-ayuda">{vista === "instituciones" ? "Todas las instituciones encontradas en tu consulta. Elige «Ver oferta» para conocer sus títulos, modalidades y estados."
        : vista === "modalidades" ? `${seleccion ? "Modalidades de la institución seleccionada." : "Compara las modalidades reportadas."} Elige «Ver oferta» para conocer los títulos y sus instituciones.`
          : vista === "formacion" ? `${seleccion ? "Formación de la institución seleccionada." : "Pregrado y posgrado de tu consulta."} Compara las ofertas activas e inactivas, o elige «Ver oferta» para explorar sus títulos.`
          : `${seleccion ? "Los niveles de la institución seleccionada distinguen" : "Cada nivel distingue"} ofertas activas e inactivas. Elige «Ver oferta» para conocer los títulos que incluye.`}</p>}
      <div className="superior-busqueda"><label htmlFor={`${id}-buscar`}>{vista === "oferta" ? "Buscar título, institución o municipio" : vista === "instituciones" ? "Buscar institución" : vista === "modalidades" ? "Buscar modalidad" : vista === "formacion" ? "Buscar grupo de formación" : "Buscar nivel académico"}</label>
        <input id={`${id}-buscar`} type="search" value={busqueda} placeholder={vista === "oferta" ? "Por ejemplo, Arquitectura" : "Escribe para filtrar"} onChange={evento => { setBusqueda(evento.target.value); setPagina(0); }} />
        {vista === "oferta" && (institucion || estado || modalidad || nivel || ciclo || busqueda) && <button type="button" className="superior-limpiar" onClick={restablecerFiltros}>Quitar filtros</button>}
      </div>
      <p className="superior-rango" role="status">{total ? `Mostrando ${desde + 1}–${Math.min(desde + FILAS_POR_PAGINA, total)} de ${formato(total)} ${vista === "oferta" ? unidad : vista === "formacion" ? "grupos de formación" : vista}` : "No hay coincidencias con estos filtros. Prueba otra búsqueda."}</p>
      <div className="superior-panel-fijo">
        {total ? <ul className="superior-lista" aria-label={vista === "oferta" ? "Oferta de educación superior" : VISTAS.find(item => item.id === vista)!.titulo}>
          {vista === "oferta" ? filtradas.slice(desde, desde + FILAS_POR_PAGINA).map((fila, indice) => <li key={desde + indice} className="superior-oferta">
            <div className="superior-nombre"><strong title={tituloOferta(fila)}>{tituloOferta(fila)}</strong><span title={texto(fila.institucion)}>{texto(fila.institucion)}</span></div>
            <div className="superior-etiquetas"><span className={`superior-estado ${normalizar(texto(fila.estado)) === "activo" ? "superior-activa" : normalizar(texto(fila.estado)) === "inactivo" ? "superior-inactiva" : ""}`}>{texto(fila.estado, "Estado no informado")}</span>
              <span title={texto(fila.nivel)}>{texto(fila.nivel, "Nivel no informado")}</span><span title={modalidadOferta(fila)}>{modalidadOferta(fila) === "No informado" ? "Modalidad no informada" : modalidadOferta(fila)}</span></div>
            <button type="button" className="superior-abrir" aria-label={`Ver detalle de ${tituloOferta(fila)} en ${texto(fila.institucion)}`} onClick={() => setFilaDetalle(fila)}>Ver detalle <Flecha diagonal /></button>
          </li>) : grupos.slice(desde, desde + FILAS_POR_PAGINA).map(grupo => <li key={grupo.nombre} className="superior-grupo">
            <strong title={grupo.nombre}>{grupo.nombre}</strong><div className="superior-conteos"><span><b>{formato(grupo.total)}</b> {unidad}</span><span><b>{formato(grupo.activos)}</b> activas</span><span><b>{formato(grupo.inactivos)}</b> inactivas</span>{grupo.sinEstado > 0 && <span>{formato(grupo.sinEstado)} sin estado informado</span>}</div>
            <button type="button" className="superior-abrir" aria-label={`Ver oferta de ${grupo.nombre}`} onClick={() => verOferta(grupo)}>Ver oferta <Flecha /></button>
          </li>)}
        </ul> : <div className="superior-vacio"><span aria-hidden="true">⌕</span><strong>Prueba con otros filtros</strong><p>La información disponible no contiene coincidencias con esta selección.</p></div>}
      </div>
      <div className="superior-paginacion"><Paginador pagina={paginaValida} total={total} cambiar={setPagina} nombre={vista === "oferta" ? "ofertas de educación superior" : vista} /></div>
    </div>
    {detalle.consulta_completa === false && <p className="superior-nota">Esta consulta incluye una parte de la oferta disponible. Acota el municipio, la institución o el título para explorarla con mayor precisión.</p>}
    {filaDetalle && <DetalleRegistro fila={filaDetalle} cerrar={() => setFilaDetalle(null)} titulo="Detalle de la oferta educativa" />}
  </section>;
}
