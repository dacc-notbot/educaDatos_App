export type Registro = Record<string, unknown>;
export type Respuesta = {
  pregunta: string;
  respuesta: string;
  resumen: string;
  datos: Registro;
  fuentes: string[];
  advertencias: string[];
};

export class ErrorConsulta extends Error {
  constructor(
    message: string,
    public esperarHasta = 0,
  ) {
    super(message);
  }
}

export function esperaDeReintento(
  valor: string | null,
  ahora = Date.now(),
): number {
  if (!valor) return ahora + 3000;
  const segundos = Number(valor);
  const fecha = Number.isFinite(segundos)
    ? ahora + segundos * 1000
    : Date.parse(valor);
  return Number.isFinite(fecha)
    ? Math.min(ahora + 86400000, Math.max(ahora, fecha))
    : ahora + 3000;
}

export async function consultar(
  pregunta: string,
  signal: AbortSignal,
): Promise<Respuesta> {
  return solicitar("/chat", { pregunta }, signal, pregunta);
}

export async function consultarColegios(
  territorio: Registro,
  signal: AbortSignal,
): Promise<Respuesta> {
  return solicitar("/colegios", {
    departamento: territorio.departamento || undefined,
    municipio: territorio.municipio || undefined,
    modo_respuesta: "lista",
  }, signal);
}

async function solicitar(
  ruta: string, payload: Registro, signal: AbortSignal, pregunta = "",
): Promise<Respuesta> {
  const base = (
    import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? "/api" : "")
  )
    .trim()
    .replace(/\/$/, "");
  if (!base)
    throw new ErrorConsulta(
      "El servicio de consultas no está disponible en este momento. Inténtalo más tarde.",
    );
  let response: Response;
  try {
    response = await fetch(`${base}${ruta}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal,
    });
  } catch (error) {
    if (signal.aborted)
      throw new ErrorConsulta(
        "La consulta tardó demasiado. Tu pregunta sigue aquí para que puedas intentarlo de nuevo.",
      );
    throw new ErrorConsulta(
      "No pudimos conectar con el servicio. Comprueba tu conexión e inténtalo de nuevo.",
    );
  }
  if (response.status === 503)
    throw new ErrorConsulta(
      "El servicio está ocupado. Puedes volver a consultar cuando termine la espera.",
      esperaDeReintento(response.headers.get("Retry-After")),
    );
  if (response.status === 422)
    throw new ErrorConsulta(
      "Revisa tu pregunta: debe contener texto y tener hasta 2000 caracteres.",
    );
  if (response.status === 502)
    throw new ErrorConsulta(
      "La fuente oficial no respondió correctamente. Tu pregunta sigue aquí para que puedas intentarlo más tarde.",
    );
  if (!response.ok)
    throw new ErrorConsulta(
      "No pudimos completar la consulta. Inténtalo más tarde.",
    );
  let data: unknown;
  try {
    data = await response.json();
  } catch {
    throw new ErrorConsulta(
      "El servicio devolvió una respuesta que no pudimos leer. Inténtalo más tarde.",
    );
  }
  if (
    !data ||
    typeof data !== "object" ||
    !("respuesta" in data) ||
    typeof data.respuesta !== "string"
  ) {
    throw new ErrorConsulta(
      "El servicio devolvió una respuesta incompleta. Inténtalo más tarde.",
    );
  }
  const resultado = data as Record<string, unknown>;
  const ciudadana = resultado.respuesta_ciudadana as Registro | undefined;
  const textos = (valor: unknown): string[] =>
    Array.isArray(valor)
      ? valor.filter((v): v is string => typeof v === "string")
      : [];
  return {
    pregunta:
      typeof resultado.pregunta === "string" ? resultado.pregunta : pregunta,
    respuesta: data.respuesta,
    resumen: typeof ciudadana?.respuesta_corta === "string" ? ciudadana.respuesta_corta : data.respuesta,
    datos:
      resultado.datos && typeof resultado.datos === "object"
        ? (resultado.datos as Registro)
        : {},
    fuentes: textos(resultado.fuentes),
    advertencias: textos(resultado.advertencias),
  };
}

export function enlacePublico(texto: string): string | null {
  try {
    const url = new URL(texto);
    return url.protocol === "https:" || url.protocol === "http:"
      ? url.href
      : null;
  } catch {
    return null;
  }
}

export function mostrarValor(valor: unknown, clave = ""): string {
  if (valor == null) return "No disponible";
  if (["vigencia_mas_reciente", "anio_usado", "a_o", "anio", "ano", "año", "vigencia", "year"].includes(clave)) {
    const anio = Number(valor);
    return Number.isInteger(anio) && anio >= 1000 && anio <= 9999 ? String(anio) : "No disponible";
  }
  if (typeof valor === "number")
    return Number.isFinite(valor)
      ? new Intl.NumberFormat("es-CO").format(valor)
      : "No disponible";
  if (typeof valor === "boolean") return valor ? "Sí" : "No";
  return typeof valor === "string" ? valor : "No disponible";
}
