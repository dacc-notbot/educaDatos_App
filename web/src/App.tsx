import {
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type FormEvent,
} from "react";
import {
  consultar,
  consultarProgramas,
  ErrorConsulta,
  mostrarValor,
  type Registro,
  type Respuesta,
} from "./api";
import ListaColegios from "./ListaColegios";
import TablaDatos from "./TablaDatos";
import ExploradorSuperior from "./ExploradorSuperior";
import OfertaSuperior from "./OfertaSuperior";
import ResumenIcetex from "./ResumenIcetex";

const ejemplos = [
  {
    tema: "Colegios",
    pregunta: "¿Cuántos colegios oficiales y privados hay en Soacha?",
    icono: "escuela",
  },
  {
    tema: "Educación superior",
    pregunta: "¿Qué títulos de educación superior se reportan en Meta?",
    icono: "libro",
  },
  {
    tema: "ICETEX",
    pregunta: "¿Qué créditos ICETEX hay en Cundinamarca?",
    icono: "credito",
  },
];

function Icono({
  nombre = "libro",
  className = "",
}: {
  nombre?: string;
  className?: string;
}) {
  const formas: Record<string, ReactNode> = {
    libro: (
      <>
        <path d="M3 5c4-1 6 0 9 2 3-2 5-3 9-2v14c-4-1-6 0-9 2-3-2-5-3-9-2V5Z" />
        <path d="M12 7v14" />
      </>
    ),
    escuela: (
      <>
        <path d="m3 10 9-6 9 6M5 10v10h14V10M9 20v-6h6v6M12 4V2" />
        <path d="M8 10h.01M16 10h.01" />
      </>
    ),
    credito: (
      <>
        <rect x="3" y="5" width="18" height="14" rx="3" />
        <path d="M3 10h18M7 15h4" />
      </>
    ),
    flecha: (
      <>
        <path d="M5 12h14m-6-6 6 6-6 6" />
      </>
    ),
    enlace: (
      <>
        <path d="M14 3h7v7M21 3 10 14M10 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5" />
      </>
    ),
  };
  return (
    <svg
      className={className}
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {formas[nombre] || formas.libro}
    </svg>
  );
}

function Resultados({ resultado, elegirPregunta, buscar }: { resultado: Respuesta; elegirPregunta: (pregunta: string) => void; buscar: (pregunta: string, parametros?: Registro) => void }) {
  const detalle = resultado.datos.detalle_consulta as Registro | undefined;
  const esColegios = !!detalle && Array.isArray(detalle.lista_establecimientos);
  const esIcetex = !!detalle?.visualizacion_icetex || Array.isArray(detalle?.comparacion_icetex);
  const esSuperior = !!detalle && Array.isArray(detalle.lista_oferta);
  // La procedencia se lee en la página; los endpoints JSON son para la API.
  const fuentes = [...new Set(resultado.fuentes.filter((texto) =>
    !/^[a-z][a-z\d+.-]*:/i.test(texto.trim()),
  ))];
  if (!fuentes.length && resultado.fuentes.some((texto) => texto.includes("datos.gov.co")))
    fuentes.push("Datos abiertos del Gobierno de Colombia");
  const indicadores: [string, string][] = [
    ["total_establecimientos_unicos", "Establecimientos"],
    ["total_instituciones_unicas", "Instituciones"],
    ["total_programas_unicos", "Programas únicos"],
    ["total_titulos_distintos", "Títulos reportados"],
    ["total_bachilleres", "Bachilleres"],
    ["total_creditos", "Créditos"],
    ["total_bachilleres_aproximado", "Bachilleres (aprox.)"],
    ["total_creditos_o_beneficiarios_aproximado", "Créditos o beneficiarios (aprox.)"],
    ["anio_usado", "Año de los datos"],
    ["vigencia_mas_reciente", "Año de los datos"],
  ];
  const visibles = (esIcetex || esSuperior ? [] : indicadores).filter(
    ([clave]) => detalle && Object.hasOwn(detalle, clave) && !(clave === "anio_usado" && Object.hasOwn(detalle, "vigencia_mas_reciente")) && !(clave === "total_programas_unicos" && detalle.identificacion_programas_confiable === false),
  );
  const sugerencias = Array.isArray(
    resultado.datos.sugerencias_de_siguiente_pregunta,
  )
    ? resultado.datos.sugerencias_de_siguiente_pregunta.filter(
        (v): v is string => typeof v === "string",
      )
    : [];
  return (
    <section className="resultado card" aria-labelledby="resultado-titulo">
      <div className="result-heading">
        <span className="eyebrow">TU CONSULTA</span>
        <span className="result-badge">Datos abiertos</span>
      </div>
      <h2 id="resultado-titulo">Esto encontramos</h2>
      <p className="pregunta-enviada">{resultado.pregunta}</p>
      <p className="respuesta-texto">{resultado.resumen}</p>
      {!esColegios && resultado.resumen !== resultado.respuesta && <details className="muestra"><summary>Ver hallazgos de la consulta</summary><p className="respuesta-texto">{resultado.respuesta}</p></details>}
      {visibles.length > 0 && (
        <dl className="indicadores">
          {visibles.map(([clave, label]) => (
            <div key={clave}>
              <dt>{label}</dt>
              <dd>{mostrarValor(detalle![clave], clave)}</dd>
            </div>
          ))}
        </dl>
      )}
      {esColegios && <ListaColegios detalle={detalle!} />}
      {esSuperior && <OfertaSuperior detalle={detalle!} buscar={buscar} />}
      {resultado.advertencias.length > 0 && (
        <aside
          className="advertencias"
          aria-label="Advertencias sobre los datos"
        >
          <details><summary>Sobre esta información ({resultado.advertencias.length})</summary>
          <ul>
            {resultado.advertencias.map((texto, i) => (
              <li key={i}>{texto}</li>
            ))}
          </ul>
          </details>
        </aside>
      )}
      {esIcetex && <ResumenIcetex detalle={detalle!} buscar={buscar} pregunta={resultado.pregunta} />}
      {!esIcetex && Array.isArray(resultado.datos.resumenes_icetex) && resultado.datos.resumenes_icetex.length > 0 && <ResumenIcetex
        detalle={{ comparacion_icetex: resultado.datos.resumenes_icetex }} buscar={buscar} pregunta="ICETEX" />}
      {esSuperior && <ExploradorSuperior detalle={detalle!} />}
      {!esColegios && !esIcetex && !esSuperior && <TablaDatos datos={resultado.datos} />}
      {fuentes.length > 0 && (
        <div className="fuentes">
          <h3>De dónde viene esta información</h3>
          <ul>
            {fuentes.map((fuente, i) => <li key={i}>{fuente}</li>)}
          </ul>
        </div>
      )}
      {!esColegios && sugerencias.length > 0 && (
        <div className="sugerencias">
          <h3>Puedes seguir explorando</h3>
          <ul>
            {sugerencias.slice(0, 3).map((s, i) => (
              <li key={i}><button type="button" className="sugerencia-pregunta" onClick={() => elegirPregunta(s)}>{s}</button></li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

export default function App() {
  const [pregunta, setPregunta] = useState("");
  const [resultado, setResultado] = useState<Respuesta | null>(null);
  const [pendiente, setPendiente] = useState(false);
  const [error, setError] = useState("");
  const [esperarHasta, setEsperarHasta] = useState(0);
  const [ahora, setAhora] = useState(Date.now());
  const campo = useRef<HTMLTextAreaElement>(null);
  const solicitud = useRef<AbortController | null>(null);
  const activo = useRef(true);
  const espera = Math.max(0, Math.ceil((esperarHasta - ahora) / 1000));
  useEffect(() => {
    activo.current = true;
    return () => {
      activo.current = false;
      solicitud.current?.abort();
    };
  }, []);
  useEffect(() => {
    if (!esperarHasta) return;
    const timer = window.setInterval(() => {
      const tiempo = Date.now();
      setAhora(tiempo);
      if (tiempo >= esperarHasta) {
        setEsperarHasta(0);
        window.clearInterval(timer);
      }
    }, 250);
    return () => window.clearInterval(timer);
  }, [esperarHasta]);

  async function enviar(event: FormEvent) {
    event.preventDefault();
    await ejecutarConsulta(pregunta);
  }
  async function ejecutarConsulta(texto: string, parametros?: Registro) {
    if (pendiente || espera > 0 || !texto.trim()) return;
    if (texto.trim().length > 2000) {
      setError("Tu pregunta debe tener hasta 2000 caracteres.");
      return;
    }
    setPendiente(true);
    setPregunta(texto);
    setError("");
    setResultado(null);
    const controller = new AbortController();
    solicitud.current = controller;
    const timer = window.setTimeout(() => controller.abort(), 180000);
    try {
      const respuesta = parametros ? await consultarProgramas(parametros, controller.signal, texto.trim()) : await consultar(texto.trim(), controller.signal);
      if (activo.current) setResultado(respuesta);
    } catch (e) {
      if (activo.current) {
        setError(
          e instanceof Error ? e.message : "No pudimos completar la consulta.",
        );
        if (e instanceof ErrorConsulta) {
          setEsperarHasta(e.esperarHasta);
          setAhora(Date.now());
        }
      }
    } finally {
      window.clearTimeout(timer);
      if (activo.current) setPendiente(false);
      solicitud.current = null;
    }
  }

  function usarEjemplo(texto: string) {
    setPregunta(texto);
    setError("");
    campo.current?.focus();
  }
  return (
    <>
      <a className="saltar" href="#consulta">
        Ir a la consulta
      </a>
      <header className="cabecera">
        <a className="marca" href="/" aria-label="EducaDatos, inicio">
          <span className="marca-icono">
            <Icono />
          </span>
          <span>
            Educa<span className="marca-acento">Datos</span>
            <small>Educación en Colombia</small>
          </span>
        </a>
        <span className="acceso">
          <i /> Abierto para todos
        </span>
      </header>
      <main>
        <section className="hero" aria-labelledby="titulo">
          <div className="hero-texto">
            <span className="eyebrow">
              <span className="colombia" aria-hidden="true" /> DATOS ABIERTOS ·
              COLOMBIA
            </span>
            <h1 id="titulo">
              Entender la educación
              <br />
              empieza con <em>una pregunta.</em>
            </h1>
            <p>
              Explora colegios, educación superior y oportunidades educativas de
              tu territorio. Información pública, en palabras claras.
            </p>
            <div className="hero-notas">
              <span>Sin registro</span>
              <span>Fuentes oficiales</span>
              <span>Acceso gratuito</span>
            </div>
          </div>
          <div className="hero-ilustracion" aria-hidden="true">
            <div className="orbita">
              <span className="orbita-punto" />
              <span className="orbita-punto otro" />
              <div className="centro-ilustracion">
                <Icono />
                <span>
                  Más datos.
                  <br />
                  Más posibilidades.
                </span>
              </div>
            </div>
            <div className="mini-tarjeta tarjeta-arriba">
              <Icono nombre="escuela" />
              <span>Tu territorio</span>
            </div>
            <div className="mini-tarjeta tarjeta-abajo">
              <Icono nombre="credito" />
              <span>Tus oportunidades</span>
            </div>
          </div>
        </section>
        <section
          id="consulta"
          className="consulta card"
          aria-labelledby="consulta-titulo"
        >
          <div className="section-heading">
            <div>
              <span className="eyebrow">EMPECEMOS</span>
              <h2 id="consulta-titulo">¿Qué quieres saber?</h2>
            </div>
            <span className="paso">01 / Pregunta y explora</span>
          </div>
          <form onSubmit={enviar}>
            <label htmlFor="pregunta">
              Escribe tu pregunta sobre educación en Colombia
            </label>
            <textarea
              ref={campo}
              id="pregunta"
              value={pregunta}
              maxLength={2000}
              rows={3}
              onChange={(event) => setPregunta(event.target.value)}
              placeholder="Por ejemplo: ¿Cuántos colegios oficiales hay en Soacha?"
              aria-describedby="ayuda-pregunta"
              disabled={pendiente}
            />
            <div className="form-footer">
              <p id="ayuda-pregunta">
                Incluye un municipio o departamento para obtener una respuesta
                más precisa.
                <span className="contador">{pregunta.length}/2000</span>
              </p>
              <button
                className="boton-consultar"
                type="submit"
                disabled={pendiente || !pregunta.trim() || espera > 0}
              >
                {pendiente
                  ? "Consultando…"
                  : espera > 0
                    ? `Espera ${espera} s`
                    : "Consultar"}
                {pendiente ? (
                  <span className="spinner" aria-hidden="true" />
                ) : (
                  <Icono nombre="flecha" />
                )}
              </button>
            </div>
          </form>
          <div role="status" aria-live="polite" aria-atomic="true">
            {pendiente && (
              <p className="estado">
                Consultando fuentes oficiales. Algunas consultas pueden tardar
                unos minutos.
              </p>
            )}
            {resultado && (
              <span className="solo-lectores">
                Respuesta disponible debajo del formulario.
              </span>
            )}
          </div>
          {error && (
            <p className="error" role="alert">
              {error}
              {espera > 0 && <span> Espera {espera} segundos.</span>}
            </p>
          )}
        </section>
        {resultado && <Resultados resultado={resultado} elegirPregunta={usarEjemplo} buscar={ejecutarConsulta} />}
        <section className="ejemplos" aria-labelledby="ejemplos-titulo">
          <div className="examples-heading">
            <h2 id="ejemplos-titulo">Una idea para comenzar</h2>
            <span>Elige una pregunta y hazla tuya</span>
          </div>
          <div className="ejemplos-grid">
            {ejemplos.map((ejemplo) => (
              <button
                key={ejemplo.tema}
                className="ejemplo"
                disabled={pendiente}
                onClick={() => usarEjemplo(ejemplo.pregunta)}
              >
                <span className="ejemplo-icono">
                  <Icono nombre={ejemplo.icono} />
                </span>
                <span className="ejemplo-tema">{ejemplo.tema}</span>
                <span className="ejemplo-pregunta">{ejemplo.pregunta}</span>
                <span className="ejemplo-accion">
                  Usar esta pregunta <Icono nombre="flecha" />
                </span>
              </button>
            ))}
          </div>
        </section>
        <section className="nota-datos">
          <span className="nota-icono">
            <Icono />
          </span>
          <div>
            <h2>Información para explorar y comprender</h2>
            <p>
              Las respuestas usan datos abiertos publicados por entidades
              oficiales en{" "}
              <a
                href="https://www.datos.gov.co/"
                target="_blank"
                rel="noopener noreferrer"
              >
                datos.gov.co
              </a>
              . La vigencia y la cobertura dependen de cada fuente. Consulta las
              advertencias y los años reportados antes de sacar conclusiones.
            </p>
          </div>
        </section>
      </main>
      <footer>
        <span className="footer-marca">EducaDatos</span>
        <span>Datos públicos. Preguntas de todos.</span>
        <a
          href="https://www.datos.gov.co/"
          target="_blank"
          rel="noopener noreferrer"
        >
          Portal de datos abiertos <Icono nombre="enlace" />
        </a>
      </footer>
    </>
  );
}
