import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { consultarTerritorios, ErrorConsulta } from "./api";
import type { CatalogoTerritorios } from "./api";
import "./SelectorTerritorio.css";

export type TerritorioSeleccionado = { departamento?: string; municipio?: string };
type Props = {
  valor: TerritorioSeleccionado;
  onChange: (valor: TerritorioSeleccionado) => void;
  onValidezChange?: (valido: boolean) => void;
};
type Opcion = { etiqueta: string; departamento: string; municipio?: string };
const normalizar = (texto = "") => {
  const limpio = texto.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[.,]/g, "").replace(/\s+/g, " ").trim();
  return ["bogota", "bogota dc"].includes(limpio) ? "bogota dc" : limpio;
};
const iguales = (a: TerritorioSeleccionado, b: TerritorioSeleccionado) =>
  a.departamento === b.departamento && a.municipio === b.municipio;

export default function SelectorTerritorio({ valor, onChange, onValidezChange }: Props) {
  const id = useId();
  const [catalogo, setCatalogo] = useState<CatalogoTerritorios | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [esperarHasta, setEsperarHasta] = useState(0);
  const [ahora, setAhora] = useState(Date.now());
  const [intento, setIntento] = useState(0);
  const [departamentoTexto, setDepartamentoTexto] = useState(valor.departamento || "");
  const [municipioTexto, setMunicipioTexto] = useState(valor.municipio || "");
  const [busqueda, setBusqueda] = useState("");
  const [abierto, setAbierto] = useState<"departamento" | "municipio" | null>(null);
  const [activo, setActivo] = useState(0);
  const [valido, setValido] = useState(true);
  const ultimoEmitido = useRef(valor);
  const ultimoCatalogo = useRef<CatalogoTerritorios | null>(null);
  const municipioInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    let vigente = true;
    const timeout = window.setTimeout(() => controller.abort(), 70000);
    setCargando(true);
    setError("");
    consultarTerritorios(controller.signal).then((datos) => {
      if (vigente) setCatalogo(datos);
    }).catch((fallo: unknown) => {
      if (!vigente) return;
      setError(fallo instanceof Error ? fallo.message : "No pudimos cargar los municipios. Vuelve a intentarlo.");
      if (fallo instanceof ErrorConsulta) setEsperarHasta(fallo.esperarHasta);
    }).finally(() => {
      window.clearTimeout(timeout);
      if (vigente) setCargando(false);
    });
    return () => { vigente = false; window.clearTimeout(timeout); controller.abort(); };
  }, [intento]);

  useEffect(() => {
    if (esperarHasta <= Date.now()) return;
    const intervalo = window.setInterval(() => setAhora(Date.now()), 1000);
    return () => window.clearInterval(intervalo);
  }, [esperarHasta]);

  useEffect(() => {
    onValidezChange?.(valido && Boolean(catalogo) && !cargando && !error);
  }, [valido, catalogo, cargando, error, onValidezChange]);

  const departamentos = useMemo(() => catalogo?.departamentos || [], [catalogo]);
  const municipios = useMemo(() => departamentos.flatMap((dep) => dep.municipios.map((mun) => ({
    departamento: dep.departamento,
    municipio: mun.municipio,
    etiqueta: `${mun.municipio} · ${dep.departamento}`,
  }))), [departamentos]);
  const departamentoActual = departamentos.find((dep) => normalizar(dep.departamento) === normalizar(valor.departamento));
  const municipiosDisponibles = departamentoActual
    ? municipios.filter((mun) => mun.departamento === departamentoActual.departamento)
    : municipios;
  const opciones: Opcion[] = (abierto === "departamento"
    ? departamentos.map((dep) => ({ etiqueta: dep.departamento, departamento: dep.departamento }))
    : municipiosDisponibles).filter((opcion) => normalizar(opcion.etiqueta).includes(normalizar(busqueda)));

  const emitir = (nuevo: TerritorioSeleccionado) => {
    ultimoEmitido.current = nuevo;
    if (!iguales(nuevo, valor)) onChange(nuevo);
  };
  const seleccionar = (opcion: Opcion) => {
    setDepartamentoTexto(opcion.departamento);
    setMunicipioTexto(opcion.municipio || "");
    setValido(true);
    setAbierto(null);
    setBusqueda("");
    emitir({ departamento: opcion.departamento, ...(opcion.municipio ? { municipio: opcion.municipio } : {}) });
  };
  const limpiar = () => {
    setDepartamentoTexto(""); setMunicipioTexto(""); setValido(true); setAbierto(null); setBusqueda(""); emitir({});
  };

  // Una ciudad sin departamento inicial se resuelve únicamente si existe una
  // coincidencia nacional. Los homónimos requieren escoger la opción completa.
  useEffect(() => {
    if (!catalogo) return;
    const cambioExterno = !iguales(valor, ultimoEmitido.current);
    if (ultimoCatalogo.current === catalogo && !cambioExterno) return;
    ultimoCatalogo.current = catalogo;
    if (cambioExterno) {
      ultimoEmitido.current = valor;
      setDepartamentoTexto(valor.departamento || "");
      setMunicipioTexto(valor.municipio || "");
      setAbierto(null);
    }
    const seleccion = valor;
    if (seleccion.municipio && !seleccion.departamento) {
      const coincidencias = municipios.filter((mun) => normalizar(mun.municipio) === normalizar(seleccion.municipio));
      if (coincidencias.length === 1) seleccionar(coincidencias[0]);
      else setValido(false);
    } else if (seleccion.departamento) {
      const departamento = departamentos.find((dep) => normalizar(dep.departamento) === normalizar(seleccion.departamento));
      const municipio = departamento?.municipios.find((mun) => normalizar(mun.municipio) === normalizar(seleccion.municipio));
      if (!departamento || (seleccion.municipio && !municipio)) setValido(false);
      else seleccionar({ departamento: departamento.departamento, municipio: municipio?.municipio, etiqueta: departamento.departamento });
    } else setValido(true);
  }, [catalogo, valor.departamento, valor.municipio]);

  const escribir = (tipo: "departamento" | "municipio", texto: string) => {
    setBusqueda(texto); setAbierto(tipo); setActivo(0);
    if (tipo === "departamento") {
      setDepartamentoTexto(texto); setMunicipioTexto("");
      const coincidencia = departamentos.find((dep) => normalizar(dep.departamento) === normalizar(texto));
      if (coincidencia) seleccionar({ departamento: coincidencia.departamento, etiqueta: coincidencia.departamento });
      else { emitir({}); setValido(!texto.trim()); }
    } else {
      setMunicipioTexto(texto);
      const coincidencias = municipiosDisponibles.filter((mun) => normalizar(mun.municipio) === normalizar(texto));
      if (coincidencias.length === 1) seleccionar(coincidencias[0]);
      else {
        emitir(valor.departamento ? { departamento: valor.departamento } : {});
        setValido(!texto.trim());
      }
    }
  };
  const abrir = (tipo: "departamento" | "municipio") => { setAbierto(tipo); setBusqueda(""); setActivo(0); };
  const teclado = (event: KeyboardEvent<HTMLInputElement>, tipo: "departamento" | "municipio") => {
    if (event.key === "Escape") { setAbierto(null); return; }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (abierto !== tipo) { abrir(tipo); return; }
      setActivo((actual) => Math.max(0, Math.min(opciones.length - 1, actual + (event.key === "ArrowDown" ? 1 : -1))));
    } else if (event.key === "Home" && abierto) { event.preventDefault(); setActivo(0); }
    else if (event.key === "End" && abierto) { event.preventDefault(); setActivo(opciones.length - 1); }
    else if (event.key === "Enter" && abierto) {
      event.preventDefault();
      if (opciones[activo]) seleccionar(opciones[activo]);
    }
  };
  useEffect(() => {
    if (abierto && opciones.length) document.getElementById(`${id}-opcion-${activo}`)?.scrollIntoView?.({ block: "nearest" });
  }, [activo, abierto, id]);

  const segundos = Math.max(0, Math.ceil((esperarHasta - ahora) / 1000));
  return <fieldset className="selector-territorio">
    <legend>¿Dónde quieres explorar?</legend>
    <p className="territorio-instruccion">Escribe un departamento o un municipio. Al elegir una ciudad encontrarás los demás municipios de su departamento.</p>
    {cargando && <p role="status">Cargando departamentos y municipios…</p>}
    {error && <div className="territorio-error" role="alert"><p>{error}</p><button type="button" disabled={segundos > 0} onClick={() => setIntento((v) => v + 1)}>{segundos > 0 ? `Reintentar en ${segundos} s` : "Reintentar municipios"}</button></div>}
    <div className="territorio-campos">
      {(["departamento", "municipio"] as const).map((tipo) => <div className="territorio-campo" key={tipo}>
        <label htmlFor={`${id}-${tipo}`}>{tipo === "departamento" ? "Departamento" : "Municipio"}</label>
        <input id={`${id}-${tipo}`} ref={tipo === "municipio" ? municipioInput : undefined} type="text" role="combobox"
          autoComplete="off" maxLength={120} placeholder={tipo === "departamento" ? "Por ejemplo, Meta" : "Escribe o elige un municipio"}
          value={tipo === "departamento" ? departamentoTexto : municipioTexto} disabled={cargando || !catalogo}
          aria-expanded={abierto === tipo} aria-autocomplete="list" aria-controls={abierto === tipo ? `${id}-opciones` : undefined}
          aria-activedescendant={abierto === tipo && opciones[activo] ? `${id}-opcion-${activo}` : undefined}
          aria-describedby={`${id}-ayuda`} aria-invalid={!valido && ((tipo === "municipio" && Boolean(municipioTexto)) || (tipo === "departamento" && !municipioTexto))}
          onChange={(e) => escribir(tipo, e.target.value)} onFocus={() => abrir(tipo)}
          onBlur={() => setAbierto(null)} onKeyDown={(e) => teclado(e, tipo)} />
        {abierto === tipo && <div className="territorio-opciones" id={`${id}-opciones`} role="listbox" aria-label={tipo === "departamento" ? "Departamentos disponibles" : "Municipios disponibles"}>
          {opciones.map((opcion, index) => <button type="button" role="option" aria-selected={index === activo} tabIndex={-1} id={`${id}-opcion-${index}`}
            key={`${opcion.departamento}-${opcion.municipio || ""}`} onMouseDown={(e) => e.preventDefault()} onClick={() => seleccionar(opcion)}>
            {opcion.etiqueta}
          </button>)}
          {!opciones.length && <p>No hay coincidencias. Revisa el nombre o busca en toda Colombia.</p>}
        </div>}
      </div>)}
    </div>
    <p id={`${id}-ayuda`} className={valido ? "territorio-ayuda" : "territorio-ayuda territorio-pendiente"} role="status">
      {!valido ? "Elige una coincidencia de la lista para aplicar la ubicación. Si hay municipios con el mismo nombre, fíjate en el departamento."
        : valor.municipio ? `${valor.municipio} pertenece a ${valor.departamento || "un departamento por confirmar"}.`
        : valor.departamento ? `Buscarás en todo ${valor.departamento}.` : "Buscarás en toda Colombia."}
    </p>
    <div className="territorio-acciones">
      {departamentoActual && <button type="button" onClick={() => { municipioInput.current?.focus(); abrir("municipio"); }}>
        Ver los {departamentoActual.municipios.length} municipios de {departamentoActual.departamento}
      </button>}
      {valor.municipio && valor.departamento && <button type="button" onClick={() => seleccionar({ departamento: valor.departamento!, etiqueta: valor.departamento! })}>Todo {valor.departamento}</button>}
      {(valor.departamento || valor.municipio || departamentoTexto || municipioTexto) && <button type="button" onClick={limpiar}>Toda Colombia</button>}
    </div>
  </fieldset>;
}
