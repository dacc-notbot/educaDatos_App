import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import App from "./App";
import { enlacePublico, esperaDeReintento, mostrarValor } from "./api";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it("permite consultar el código DANE de un colegio y buscar por ese identificador", async () => {
  // jsdom no implementa dialog; Chromium verifica el diálogo nativo.
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", { configurable: true, value: function (this: HTMLDialogElement) { this.setAttribute("open", ""); } });
  Object.defineProperty(HTMLDialogElement.prototype, "close", { configurable: true, value: function (this: HTMLDialogElement) { this.removeAttribute("open"); } });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respuestaColegios()));
  render(<App />);
  preguntar("Colegios en Villavicencio");
  await screen.findByRole("list", { name: "Listado de colegios" });
  fireEvent.click(screen.getByRole("button", { name: "Consultar código DANE de Colegio 01" }));
  expect(screen.getByRole("dialog", { name: "Código DANE del colegio" })).toBeTruthy();
  expect(screen.getByText("Código DANE")).toBeTruthy();
  expect(screen.getByText("1", { selector: "dd" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Cerrar" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  fireEvent.change(screen.getByLabelText("Buscar colegio por nombre o código DANE"), { target: { value: "61" } });
  expect(screen.getByRole("button", { name: "Consultar código DANE de Colegio 61" })).toBeTruthy();
});

it("pagina los registros de otras fuentes sin eliminar los posteriores a diez y cambia de colección", async () => {
  const filas = Array.from({ length: 17 }, (_, i) => ({ titulo_obtenido: `Título ${i + 1}`, institucion: "Universidad", anio: 2025 }));
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ respuesta: "Títulos reportados.", datos: {
    colecciones: [
      { titulo: "Títulos", filas, es_muestra: true },
      { titulo: "Créditos", filas: [{ institucion: "Instituto", cantidad: 0 }], es_muestra: true },
    ],
  } }), { status: 200 })));
  render(<App />);
  preguntar("Educación superior en Meta");
  await screen.findByRole("table", { name: "Títulos" });
  expect(screen.getByText("Título 5")).toBeTruthy();
  expect(screen.queryByText("Título 6")).toBeNull();
  expect(screen.getByText(/no el total de la fuente/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Ir a la página"), { target: { value: "4" } });
  expect(screen.getByText("Título 17")).toBeTruthy();
  expect(screen.queryByText("Título 1")).toBeNull();
  fireEvent.change(screen.getByLabelText("Información para explorar"), { target: { value: "1" } });
  expect(screen.getByRole("table", { name: "Créditos" })).toBeTruthy();
  expect(screen.getByText("0", { selector: ".celda-datos" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Siguiente" })).toBeNull();
});

it("la orientación ofrece preguntas editables sin enviarlas automáticamente", async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ respuesta: "EducaDatos presenta información de fuentes oficiales.", datos: {
    sugerencias_de_siguiente_pregunta: ["Colegios en Villavicencio"],
  } }), { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
  render(<App />);
  preguntar("¿Qué opinas de la educación?");
  await screen.findByText("EducaDatos presenta información de fuentes oficiales.");
  fireEvent.click(screen.getByRole("button", { name: "Colegios en Villavicencio" }));
  expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("Colegios en Villavicencio");
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

it("presenta modalidad y estados por nivel, y busca por ubicación explícita sin confundir municipios", async () => {
  const filas = [
    { titulo_obtenido: "INGENIERO DE SISTEMAS", institucion: "Universidad A", nivel: "Universitaria", ciclo: "Pregrado", estado: "Activo", modalidad: "Presencial", metodologia_modalidad: "Presencial" },
    { titulo_obtenido: "INGENIERO DE SISTEMAS", institucion: "Universidad B", nivel: "Universitaria", ciclo: "Pregrado", estado: "Inactivo", modalidad: "Virtual", metodologia_modalidad: "Virtual" },
  ];
  const datos = {
    detalle_consulta: { lista_oferta: filas, territorio: { departamento: "Meta" }, consulta_completa: true, identificacion_programas_confiable: false,
      total_programas_unicos: null, total_titulos_distintos: 1,
      procedencia_oferta: { anio_registro: null, fecha_actualizacion: "2025-01-14", descripcion_ciudadana: "Información del MEN en Datos Abiertos del Gobierno de Colombia. Última actualización de los datos: 14 de enero de 2025." },
      resumen_oferta: { unidad_conteo: "ofertas publicadas", total_ofertas: 2, por_estado: [{ estado: "Activo", total: 1 }, { estado: "Inactivo", total: 1 }],
        por_nivel: [{ nivel: "Universitaria", total: 2, activos: 1, inactivos: 1, sin_estado: 0 }],
        por_modalidad: [{ modalidad: "Presencial", total: 1, activos: 1, inactivos: 0, sin_estado: 0 }, { modalidad: "Virtual", total: 1, activos: 0, inactivos: 1, sin_estado: 0 }],
        por_ciclo: [{ ciclo: "Pregrado", total: 2, activos: 1, inactivos: 1, sin_estado: 0 }],
        instituciones: [{ institucion: "Universidad A", total_ofertas: 1, activos: 1, inactivos: 0, sin_estado: 0 }, { institucion: "Universidad B", total_ofertas: 1, activos: 0, inactivos: 1, sin_estado: 0 }],
      },
    },
  };
  const fetchMock = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ respuesta: "Oferta de educación superior en Meta.", datos }), { status: 200 }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ departamentos: [{ departamento: "Meta", municipios: [{ municipio: "Villavicencio" }, { municipio: "Acacías" }] }], fuente: "MEN", anio: 2024 }), { status: 200 }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ respuesta: "Arquitectura en Colombia." }), { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
  render(<App />);
  preguntar("Educación superior en Meta");
  await screen.findByRole("list", { name: "Oferta de educación superior" });
  await screen.findByRole("button", { name: "Ver los 2 municipios de Meta" });
  expect(screen.getByRole("table", { name: "Oferta por nivel" })).toBeTruthy();
  expect(screen.getByRole("columnheader", { name: "Activas" })).toBeTruthy();
  expect(screen.getByRole("columnheader", { name: "Inactivas" })).toBeTruthy();
  expect(screen.getByText(/14 de enero de 2025/)).toBeTruthy();
  expect(screen.queryByText(/no permite identificar de forma fiable/)).toBeNull();
  expect(screen.queryByText("Programas únicos")).toBeNull();
  fireEvent.change(screen.getByLabelText("Estado de la oferta"), { target: { value: "Inactivo" } });
  expect(screen.getByRole("list", { name: "Oferta de educación superior" }).textContent).toContain("Universidad B");
  expect(screen.getByRole("list", { name: "Oferta de educación superior" }).textContent).not.toContain("Universidad A");
  expect(screen.getByRole("list", { name: "Oferta de educación superior" }).textContent).toContain("Virtual");
  fireEvent.change(screen.getByLabelText("¿Qué programa o título buscas?"), { target: { value: "Arquitectura" } });
  fireEvent.click(screen.getByRole("button", { name: "Toda Colombia" }));
  fireEvent.click(screen.getByRole("button", { name: /Explorar oferta/ }));
  await screen.findByText("Arquitectura en Colombia.");
  expect(fetchMock.mock.calls[2][0]).toBe("/api/programas-superior");
  expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toEqual({ texto: "Arquitectura" });
});

function preguntar(texto = "Colegios en Soacha") {
  fireEvent.change(
    screen.getByLabelText("Escribe tu pregunta sobre educación en Colombia"),
    { target: { value: texto } },
  );
  fireEvent.click(screen.getByRole("button", { name: "Consultar" }));
}

describe("Consulta ciudadana", () => {
  it("permite elegir una pregunta y editarla antes de enviar, sin registro", () => {
    render(<App />);
    const boton = screen.getByRole("button", {
      name: "Consultar",
    }) as HTMLButtonElement;
    expect(boton.disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: /Colegios.*Soacha/ }));
    expect(
      (screen.getByRole("textbox") as HTMLTextAreaElement).value,
    ).toContain("Soacha");
    expect(boton.disabled).toBe(false);
  });

  it("envía JSON, bloquea envíos duplicados y muestra fuentes, advertencias y conteos null", async () => {
    let resolver!: (response: Response) => void;
    const fetchMock = vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          resolver = resolve;
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    preguntar();
    expect(
      (
        screen.getByRole("button", {
          name: "Consultando…",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    expect(fetchMock.mock.calls).toHaveLength(1);
    resolver(
      new Response(
        JSON.stringify({
          pregunta: "Colegios en Soacha",
          respuesta: "Se encontraron 219 establecimientos.",
          datos: {
            detalle_consulta: {
              total_establecimientos_unicos: 219,
              total_programas_unicos: null,
            },
            resultados_muestra: [{ municipio: "Soacha", matricula: 0 }],
          },
          fuentes: [
            "Ministerio de Educación",
            "https://www.datos.gov.co/resource/cfw5-qzt5.json",
            "javascript:alert(1)",
          ],
          advertencias: ["La fuente no identifica programas únicos."],
        }),
        { status: 200 },
      ),
    );
    await screen.findByText("Se encontraron 219 establecimientos.");
    expect(screen.getByText("No disponible")).toBeTruthy();
    expect(
      screen.getByText("La fuente no identifica programas únicos."),
    ).toBeTruthy();
    expect(screen.getByText("Ministerio de Educación")).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Consultar fuente oficial" })).toBeNull();
    expect(document.querySelector('a[href$="cfw5-qzt5.json"]')).toBeNull();
    expect(document.querySelector('a[href^="javascript:"]')).toBeNull();
    expect(
      JSON.parse(
        (fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1]
          .body as string,
      ),
    ).toEqual({ pregunta: "Colegios en Soacha" });
    expect(
      (screen.getByRole("button", { name: "Consultar" }) as HTMLButtonElement)
        .disabled,
    ).toBe(false);
  });

  it("conserva la pregunta cuando falla la fuente y permite reintentar", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("{}", { status: 502 })),
    );
    render(<App />);
    preguntar("ICETEX en Meta");
    await screen.findByRole("alert");
    expect(screen.getByRole("alert").textContent).toContain("fuente oficial");
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe(
      "ICETEX en Meta",
    );
    expect(
      (screen.getByRole("button", { name: "Consultar" }) as HTMLButtonElement)
        .disabled,
    ).toBe(false);
  });

  it("respeta Retry-After ante sobrecarga y no reenvía automáticamente", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response("{}", { status: 503, headers: { "Retry-After": "1" } }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    preguntar();
    await screen.findByRole("alert");
    expect(
      (screen.getByRole("button", { name: /Espera/ }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    await waitFor(
      () =>
        expect(
          (
            screen.getByRole("button", {
              name: "Consultar",
            }) as HTMLButtonElement
          ).disabled,
        ).toBe(false),
      { timeout: 2000 },
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("informa de un error de red sin perder la pregunta", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );
    render(<App />);
    preguntar();
    expect((await screen.findByRole("alert")).textContent).toContain(
      "conexión",
    );
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe(
      "Colegios en Soacha",
    );
  });

  it("no presenta una respuesta ilegible como resultado correcto", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(new Response("html incorrecto", { status: 200 })),
    );
    render(<App />);
    preguntar();
    expect((await screen.findByRole("alert")).textContent).toContain(
      "no pudimos leer",
    );
    expect(screen.queryByText("Esto encontramos")).toBeNull();
  });

  it("renderiza contenido de la fuente como texto, sin ejecutar HTML", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            JSON.stringify({ respuesta: "<img src=x onerror=alert(1)>" }),
            { status: 200 },
          ),
        ),
    );
    render(<App />);
    preguntar();
    await screen.findByText("<img src=x onerror=alert(1)>");
    expect(document.querySelector("img")).toBeNull();
  });
});

it("distingue cero de dato no disponible", () => {
  expect(mostrarValor(null)).toBe("No disponible");
  expect(mostrarValor(0)).toBe("0");
  expect(mostrarValor(Number.NaN)).toBe("No disponible");
  expect(mostrarValor(2025, "vigencia_mas_reciente")).toBe("2025");
  expect(mostrarValor("2025.0", "a_o")).toBe("2025");
  expect(mostrarValor(12525)).toBe("12.525");
});

const lista = Array.from({ length: 61 }, (_, i) => ({
  nombre_establecimiento: `Colegio ${String(i + 1).padStart(2, "0")}`,
  codigo_establecimiento: String(i + 1), tipo: i < 30 ? "Público" : "Privado",
}));
function respuestaColegios(modo = "lista", sector: string | null = null) {
  return new Response(JSON.stringify({
    respuesta: "Hay 61 colegios.\n\nHallazgos principales:\n- Detalle técnico.",
    respuesta_ciudadana: { respuesta_corta: "Hay 61 colegios." },
    datos: { detalle_consulta: {
      modo_respuesta: modo, sector_consultado: sector, consulta_completa: true,
      total_establecimientos_unicos: 61, vigencia_mas_reciente: 2025,
      territorio: { departamento: "Meta", municipio: "Villavicencio" },
      lista_establecimientos: modo === "lista" ? lista : [],
    } },
    fuentes: ["MEN", "https://www.datos.gov.co/resource/cfw5-qzt5.json"],
  }), { status: 200 });
}

it("muestra una lista de nombres y tipos, pagina todos los colegios y busca por nombre", async () => {
  const fetchMock = vi.fn().mockResolvedValue(respuestaColegios());
  vi.stubGlobal("fetch", fetchMock);
  render(<App />);
  preguntar("Colegios en Villavicencio");
  await screen.findByRole("list", { name: "Listado de colegios" });
  expect(screen.getByText("2025")).toBeTruthy();
  expect(screen.queryByText("2.025")).toBeNull();
  expect(screen.queryByText(/Detalle técnico/)).toBeNull();
  expect(screen.queryByText(/Ver muestra de registros/)).toBeNull();
  expect(screen.getByText("Colegio 05")).toBeTruthy();
  expect(screen.queryByText("Colegio 06")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Siguiente" }));
  expect(screen.getByText("Colegio 06")).toBeTruthy();
  expect(screen.queryByText("Colegio 01")).toBeNull();
  fireEvent.change(screen.getByLabelText("Buscar colegio por nombre o código DANE"), { target: { value: "Colegio 61" } });
  expect(screen.getByText("Colegio 61")).toBeTruthy();
  expect(screen.queryByText("Colegio 06")).toBeNull();
  expect(screen.queryByRole("button", { name: "Siguiente" })).toBeNull();
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

it("responde a cuántos con el número y carga el directorio al elegir un tipo, sin repetir solicitudes", async () => {
  const fetchMock = vi.fn().mockResolvedValueOnce(respuestaColegios("conteo"))
    .mockResolvedValueOnce(respuestaColegios());
  vi.stubGlobal("fetch", fetchMock);
  render(<App />);
  preguntar("¿Cuántos colegios hay en Villavicencio?");
  await screen.findByText("Hay 61 colegios.");
  expect(screen.queryByRole("list", { name: "Listado de colegios" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Conocer privados" }));
  await screen.findByText("Colegio 31");
  expect(screen.queryByText("Colegio 01")).toBeNull();
  const [url, options] = fetchMock.mock.calls[1];
  expect(url).toBe("/api/colegios");
  expect(JSON.parse(options.body)).toEqual({ departamento: "Meta", municipio: "Villavicencio", modo_respuesta: "lista" });
  fireEvent.click(screen.getByRole("button", { name: "Conocer públicos" }));
  expect(screen.getByText("Colegio 01")).toBeTruthy();
  expect(screen.queryByText("Colegio 31")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Conocerlos todos" }));
  expect(screen.getByText("Página 1 de 13")).toBeTruthy();
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

it("conserva el conteo ante un fallo al cargar los colegios y permite reintentar", async () => {
  const fetchMock = vi.fn().mockResolvedValueOnce(respuestaColegios("conteo"))
    .mockResolvedValueOnce(new Response("{}", { status: 502 }))
    .mockResolvedValueOnce(respuestaColegios());
  vi.stubGlobal("fetch", fetchMock);
  render(<App />);
  preguntar("¿Cuántos colegios hay en Villavicencio?");
  await screen.findByText("Hay 61 colegios.");
  fireEvent.click(screen.getByRole("button", { name: "Conocerlos todos" }));
  expect((await screen.findByRole("alert")).textContent).toContain("fuente oficial");
  expect(screen.getByText("Hay 61 colegios.")).toBeTruthy();
  expect(screen.queryByText("No se encontraron colegios con este filtro.")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Conocerlos todos" }));
  await screen.findByRole("list", { name: "Listado de colegios" });
  expect(screen.queryByRole("alert")).toBeNull();
});

it("respeta la espera al cargar un directorio ocupado sin consultar automáticamente", async () => {
  const fetchMock = vi.fn().mockResolvedValueOnce(respuestaColegios("conteo"))
    .mockResolvedValueOnce(new Response("{}", { status: 503, headers: { "Retry-After": "1" } }));
  vi.stubGlobal("fetch", fetchMock);
  render(<App />);
  preguntar("¿Cuántos colegios hay en Villavicencio?");
  await screen.findByText("Hay 61 colegios.");
  fireEvent.click(screen.getByRole("button", { name: "Conocerlos todos" }));
  await screen.findByRole("alert");
  expect((screen.getByRole("button", { name: "Conocerlos todos" }) as HTMLButtonElement).disabled).toBe(true);
  await waitFor(() => expect((screen.getByRole("button", { name: "Conocerlos todos" }) as HTMLButtonElement).disabled).toBe(false), { timeout: 2000 });
  expect(fetchMock).toHaveBeenCalledTimes(2);
  expect(screen.queryByRole("list", { name: "Listado de colegios" })).toBeNull();
});

it("acepta solo enlaces web y las dos formas de Retry-After", () => {
  expect(enlacePublico("javascript:alert(1)")).toBeNull();
  expect(enlacePublico("https://www.datos.gov.co/")).toBe(
    "https://www.datos.gov.co/",
  );
  expect(esperaDeReintento("3", 1000)).toBe(4000);
  const fecha = new Date(Date.now() + 10000).toUTCString();
  expect(esperaDeReintento(fecha)).toBe(Date.parse(fecha));
});

function respuestaIcetex(total: number | null = 25) {
  return new Response(JSON.stringify({ pregunta: "ICETEX de pregrado en Meta en 2025", respuesta: "ICETEX reporta nuevos beneficiarios.", datos: {
    detalle_consulta: { tipo_credito: "otorgados", visualizacion_icetex: {
      unidad: "Nuevos beneficiarios de crédito", explicacion: "Suma los beneficiarios reportados; no son filas descargadas.", territorio: "Meta", anio: 2025, total,
      cobertura_disponible: true, serie_anual: Array.from({ length: 11 }, (_, i) => ({ anio: 2015 + i, cantidad: i * 10 })),
      distribuciones: [
        { clave: "nivel_de_formacion", titulo: "Nivel de formación", nota: "Nivel reportado.", permite_grafico: true, filas: Array.from({ length: 7 }, (_, i) => ({ categoria: `Nivel ${i + 1}`, cantidad: i === 0 ? 0 : i })) },
        { clave: "rango_del_valor_total", titulo: "Rango de desembolso", nota: "Códigos de rango, no montos exactos en pesos.", permite_grafico: false, filas: [{ categoria: "I", cantidad: 25 }] },
      ],
    } },
  } }), { status: 200 });
}

it("presenta ICETEX con unidades precisas, gráficos y tablas paginadas sin confundir rangos con dinero", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respuestaIcetex()));
  render(<App />);
  preguntar("ICETEX en Meta");
  await screen.findByRole("img", { name: /Nivel de formación/ });
  expect(screen.queryByText("Créditos o beneficiarios (aprox.)")).toBeNull();
  expect(screen.queryByText("Registros de ICETEX")).toBeNull();
  expect(screen.getByText("2025", { selector: "dd" })).toBeTruthy();
  expect(screen.queryByText("2.025")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Tabla" }));
  expect(screen.getByRole("table", { name: "ICETEX: Nivel de formación" })).toBeTruthy();
  expect(screen.getByText("Nivel 5")).toBeTruthy();
  expect(screen.queryByText("Nivel 6")).toBeNull();
  expect(screen.getByText("0", { selector: "td" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Siguiente" }));
  expect(screen.getByText("Nivel 7")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Ver cifras por"), { target: { value: "rango_del_valor_total" } });
  expect(screen.getByRole("table", { name: "ICETEX: Rango de desembolso" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Gráfico" })).toBeNull();
  expect(screen.getByText(/Códigos de rango, no montos exactos/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Ver cifras por"), { target: { value: "serie_anual" } });
  fireEvent.change(screen.getByLabelText("Ir a la página"), { target: { value: "3" } });
  expect(screen.getByText("2025", { selector: "button" })).toBeTruthy();
});

it("conserva el filtro al cambiar el año de ICETEX y distingue total cero de dato ausente", async () => {
  const fetchMock = vi.fn().mockResolvedValueOnce(respuestaIcetex(0))
    .mockResolvedValueOnce(new Response(JSON.stringify({ respuesta: "Consulta de 2023." }), { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
  render(<App />);
  preguntar("ICETEX de pregrado en Meta en 2025");
  await screen.findByText("ICETEX en cifras");
  expect(screen.getByText("0", { selector: "dd" })).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Año de ICETEX"), { target: { value: "2023" } });
  await screen.findByText("Consulta de 2023.");
  const texto = JSON.parse(fetchMock.mock.calls[1][1].body).pregunta;
  expect(texto).toContain("pregrado");
  expect(texto).toContain("2023");
  expect(texto).not.toContain("2025");
});
