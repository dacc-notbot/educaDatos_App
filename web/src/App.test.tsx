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
    expect(
      screen
        .getByRole("link", { name: "Consultar fuente oficial" })
        .getAttribute("href"),
    ).toContain("datos.gov.co");
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
