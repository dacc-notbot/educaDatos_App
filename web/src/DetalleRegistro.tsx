import { useEffect, useRef } from "react";
import { mostrarValor, type Registro } from "./api";

export const etiqueta = (clave: string) => ({
  nombre_establecimiento: "Colegio", codigo_establecimiento: "Código DANE",
  nombre_institucion: "Institución", municipio: "Municipio",
  departamento: "Departamento", tipo: "Tipo", valor: "Categoría", conteo: "Cantidad",
  cantidad: "Cantidad", a_o: "Año", anio: "Año", anio_usado: "Año", vigencia: "Año",
  grupo_estadistico: "Grupo de municipios", distancia_estandarizada: "Distancia estadística",
  titulo_obtenido: "Título otorgado", institucion: "Institución", nivel: "Nivel académico", estado: "Estado",
  programa: "Programa", metodologia_modalidad: "Modalidad", area_conocimiento: "Área de conocimiento",
  descripcion: "Descripción", categoria: "Categoría", matricula: "Matrícula", secretaria_o_etc: "Secretaría de Educación",
} as Record<string, string>)[clave] || clave.replace(/_/g, " ");

export default function DetalleRegistro({ fila, cerrar, titulo = "Detalle del registro" }: {
  fila: Registro; cerrar: () => void; titulo?: string;
}) {
  const modal = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialogo = modal.current!;
    dialogo.showModal();
    return () => dialogo.close();
  }, []);
  return <dialog ref={modal} className="detalle-registro" aria-labelledby="detalle-titulo" onCancel={cerrar}>
    <h2 id="detalle-titulo">{titulo}</h2>
    <dl>{Object.entries(fila).filter(([, valor]) => valor == null || ["number", "string", "boolean"].includes(typeof valor)).map(([clave, valor]) =>
      <div key={clave}><dt>{etiqueta(clave)}</dt><dd>{/codigo|cod_dane/.test(clave) ? (valor != null && valor !== "" ? String(valor) : "No informado en la fuente") : mostrarValor(valor, clave)}</dd></div>,
    )}</dl>
    <button type="button" className="boton-consultar" onClick={cerrar}>Cerrar</button>
  </dialog>;
}
