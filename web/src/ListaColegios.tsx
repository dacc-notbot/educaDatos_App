import { useEffect, useRef, useState } from "react";
import { consultarColegios, ErrorConsulta, mostrarValor, type Registro } from "./api";

type Filtro = "Público" | "Privado" | "Todos";
const TAMANO_PAGINA = 25;
const normalizar = (texto: string) => texto.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

function colegios(detalle: Registro): Registro[] {
  return Array.isArray(detalle.lista_establecimientos)
    ? detalle.lista_establecimientos.filter((fila): fila is Registro => !!fila && typeof fila === "object")
    : [];
}

function tipoColegio(fila: Registro): string {
  if (typeof fila.tipo === "string") return fila.tipo;
  const sector = String(fila.sector || "").toUpperCase().replace(/_/g, " ");
  return sector === "OFICIAL" ? "Público" : sector === "NO OFICIAL" ? "Privado" : "Sin dato";
}

export default function ListaColegios({ detalle }: { detalle: Registro }) {
  const inicial: Filtro | null = detalle.modo_respuesta !== "lista" ? null
    : detalle.sector_consultado === "OFICIAL" ? "Público"
    : detalle.sector_consultado === "NO_OFICIAL" ? "Privado" : "Todos";
  const [filtro, setFiltro] = useState<Filtro | null>(inicial);
  const [completo, setCompleto] = useState<Registro | null>(inicial === "Todos" ? detalle : null);
  const [busqueda, setBusqueda] = useState("");
  const [pagina, setPagina] = useState(0);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");
  const [esperarHasta, setEsperarHasta] = useState(0);
  const [ahora, setAhora] = useState(Date.now());
  const solicitud = useRef<AbortController | null>(null);
  const activo = useRef(true);
  const espera = Math.max(0, Math.ceil((esperarHasta - ahora) / 1000));
  useEffect(() => {
    activo.current = true;
    return () => { activo.current = false; solicitud.current?.abort(); };
  }, []);
  useEffect(() => {
    if (!esperarHasta) return;
    const timer = window.setInterval(() => {
      const tiempo = Date.now();
      setAhora(tiempo);
      if (tiempo >= esperarHasta) { setEsperarHasta(0); window.clearInterval(timer); }
    }, 250);
    return () => window.clearInterval(timer);
  }, [esperarHasta]);

  async function elegir(nuevo: Filtro) {
    if (solicitud.current || espera) return;
    setError("");
    if (completo) { setFiltro(nuevo); setBusqueda(""); setPagina(0); return; }
    const territorio = detalle.territorio as Registro | undefined;
    if (!territorio || (!territorio.departamento && !territorio.municipio)) {
      setError("Vuelve a consultar indicando tu ciudad para conocer los colegios.");
      return;
    }
    setCargando(true);
    const controller = new AbortController();
    solicitud.current = controller;
    const timer = window.setTimeout(() => controller.abort(), 180000);
    try {
      const respuesta = await consultarColegios(territorio, controller.signal);
      const datos = respuesta.datos.detalle_consulta as Registro | undefined;
      if (!datos || !Array.isArray(datos.lista_establecimientos) || datos.consulta_completa !== true)
        throw new Error("No pudimos obtener el listado completo. Inténtalo más tarde.");
      if (activo.current) {
        setCompleto(datos); setFiltro(nuevo); setBusqueda(""); setPagina(0);
      }
    } catch (e) {
      if (activo.current) {
        setError(e instanceof Error ? e.message : "No pudimos obtener los colegios.");
        if (e instanceof ErrorConsulta) { setEsperarHasta(e.esperarHasta); setAhora(Date.now()); }
      }
    } finally {
      window.clearTimeout(timer);
      solicitud.current = null;
      if (activo.current) setCargando(false);
    }
  }

  const datos = completo || detalle;
  const lista = colegios(datos).filter((fila) =>
    (filtro === "Todos" || tipoColegio(fila) === filtro) &&
    normalizar(String(fila.nombre_establecimiento || "")).includes(normalizar(busqueda.trim())),
  );
  const paginas = Math.max(1, Math.ceil(lista.length / TAMANO_PAGINA));
  const desde = pagina * TAMANO_PAGINA;
  return (
    <section className="directorio" aria-labelledby="directorio-titulo">
      <h3 id="directorio-titulo">Conoce los colegios</h3>
      <div className="filtros-colegios" role="group" aria-label="Tipo de colegio">
        {(["Público", "Privado", "Todos"] as const).map((tipo) => (
          <button key={tipo} type="button" aria-pressed={filtro === tipo}
            disabled={cargando || espera > 0} onClick={() => elegir(tipo)}>
            {tipo === "Público" ? "Conocer públicos" : tipo === "Privado" ? "Conocer privados" : "Conocerlos todos"}
          </button>
        ))}
      </div>
      {cargando && <p role="status">Estamos consultando el listado de colegios…</p>}
      {error && <p className="error" role="alert">{error}{espera > 0 && ` Puedes reintentar en ${espera} segundos.`}</p>}
      {filtro && (
        <>
          <p className="directorio-vigencia">Colegios {filtro === "Todos" ? "públicos y privados" : filtro.toLowerCase() + "s"} · Año {mostrarValor(datos.vigencia_mas_reciente, "vigencia_mas_reciente")}</p>
          <label className="buscar-colegio">Buscar colegio por nombre
            <input type="search" value={busqueda} placeholder="Escribe el nombre del colegio"
              onChange={(event) => { setBusqueda(event.target.value); setPagina(0); }} />
          </label>
          <p className="resumen-lista" role="status">
            {lista.length ? `Mostrando ${desde + 1}–${Math.min(desde + TAMANO_PAGINA, lista.length)} de ${mostrarValor(lista.length)} colegios` : "No se encontraron colegios con este filtro."}
          </p>
          {lista.length > 0 && (
            <>
              <div className="lista-encabezado" aria-hidden="true"><span>Colegio</span><span>Tipo</span></div>
              <ul className="lista-colegios" aria-label="Listado de colegios">
                {lista.slice(desde, desde + TAMANO_PAGINA).map((fila, i) => (
                  <li key={String(fila.codigo_establecimiento || fila.nombre_establecimiento) + i}>
                    <span>{String(fila.nombre_establecimiento || "Nombre no informado")}</span>
                    <span className="tipo-colegio">{tipoColegio(fila)}</span>
                  </li>
                ))}
              </ul>
              {paginas > 1 && <nav className="paginas-colegios" aria-label="Páginas de colegios">
                <button type="button" disabled={pagina === 0} onClick={() => setPagina(pagina - 1)}>Anterior</button>
                <span>Página {pagina + 1} de {paginas}</span>
                <button type="button" disabled={pagina + 1 >= paginas} onClick={() => setPagina(pagina + 1)}>Siguiente</button>
              </nav>}
            </>
          )}
        </>
      )}
    </section>
  );
}
