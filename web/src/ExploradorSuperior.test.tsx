import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import ExploradorSuperior from "./ExploradorSuperior";
import type { Registro } from "./api";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

function ejemplo(): Registro {
  const lista = Array.from({ length: 17 }, (_, indice) => ({
    titulo_obtenido: `Título ${indice + 1}`,
    institucion: indice < 12 ? "Universidad del territorio" : "Instituto tecnológico",
    nivel: indice < 12 ? "Universitaria" : "Maestría",
    estado: indice % 2 ? "Inactivo" : "Activo",
    metodologia_modalidad: indice % 3 ? "Presencial" : "Virtual",
    municipio: "Villavicencio", departamento: "Meta",
  }));
  return { lista_oferta: lista, consulta_completa: true, resumen_oferta: {
    unidad_conteo: "ofertas publicadas", total_ofertas: 17,
    instituciones: [
      { institucion: "Universidad del territorio", total_ofertas: 12, activos: 6, inactivos: 6, sin_estado: 0 },
      { institucion: "Instituto tecnológico", total_ofertas: 5, activos: 3, inactivos: 2, sin_estado: 0 },
    ],
    por_modalidad: [
      { modalidad: "Presencial", total: 11, activos: 6, inactivos: 5, sin_estado: 0 },
      { modalidad: "Virtual", total: 6, activos: 3, inactivos: 3, sin_estado: 0 },
    ],
    por_nivel: [
      { nivel: "Universitaria", total: 12, activos: 6, inactivos: 6, sin_estado: 0 },
      { nivel: "Maestría", total: 5, activos: 3, inactivos: 2, sin_estado: 0 },
    ],
  } };
}

describe("explorador de educación superior", () => {
  it("pagina toda la oferta y muestra la modalidad sin columnas técnicas ni conteos de programas únicos", () => {
    render(<ExploradorSuperior detalle={ejemplo()} />);
    const listado = screen.getByRole("list", { name: "Oferta de educación superior" });
    expect(within(listado).getAllByRole("listitem")).toHaveLength(5);
    expect(within(listado).getByText("Título 5")).toBeTruthy();
    expect(within(listado).queryByText("Título 6")).toBeNull();
    expect(within(listado).getAllByText("Virtual")).toHaveLength(2);
    expect(screen.queryByText("Cantidad")).toBeNull();
    expect(screen.queryByText(/muestra o un resumen/)).toBeNull();
    fireEvent.change(screen.getByLabelText("Ir a la página"), { target: { value: "4" } });
    expect(within(listado).getByText("Título 17")).toBeTruthy();
    expect(within(listado).getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByRole("status").textContent).toContain("16–17 de 17 ofertas publicadas");
  });

  it("combina filtros de estado y modalidad y vuelve a la primera página al cambiar la selección", () => {
    render(<ExploradorSuperior detalle={ejemplo()} />);
    fireEvent.click(screen.getByRole("button", { name: "Siguiente" }));
    fireEvent.change(screen.getByLabelText("Estado de la oferta"), { target: { value: "Inactivo" } });
    expect(screen.getByText("Página 1 de 2")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Modalidad del programa"), { target: { value: "Virtual" } });
    const listado = screen.getByRole("list", { name: "Oferta de educación superior" });
    expect(within(listado).getAllByRole("listitem")).toHaveLength(3);
    expect(within(listado).getAllByText("Inactivo")).toHaveLength(3);
    expect(within(listado).queryByText("Activo")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Quitar filtros" }));
    expect(within(listado).getAllByRole("listitem")).toHaveLength(5);
    expect(screen.getByText("Página 1 de 4")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Nivel académico de la oferta"), { target: { value: "Maestría" } });
    fireEvent.change(screen.getByLabelText("Institución de la oferta"), { target: { value: "Universidad del territorio" } });
    expect((screen.getByLabelText("Nivel académico de la oferta") as HTMLSelectElement).value).toBe("");
    expect(screen.getByRole("status").textContent).toContain("1–5 de 12 ofertas publicadas");
    expect(within(listado).queryByText("Maestría")).toBeNull();
  });

  it("abre la oferta de una institución en el mismo panel y permite explorar pregrado o posgrado", () => {
    render(<ExploradorSuperior detalle={ejemplo()} />);
    fireEvent.click(screen.getByRole("tab", { name: "Instituciones" }));
    const listado = screen.getByRole("list", { name: "Instituciones" });
    expect(within(listado).getByText("Universidad del territorio")).toBeTruthy();
    expect(within(listado).getAllByText("ofertas publicadas", { exact: false })).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: "Ver oferta de Instituto tecnológico" }));
    expect(screen.getByRole("tab", { name: "Programas y títulos" }).getAttribute("aria-selected")).toBe("true");
    expect(screen.getByText(/En esta consulta: 5 ofertas publicadas · 3 activas · 2 inactivas/)).toBeTruthy();
    const ofertas = screen.getByRole("list", { name: "Oferta de educación superior" });
    expect(within(ofertas).getAllByRole("listitem")).toHaveLength(5);
    expect(within(ofertas).queryByText("Título 1")).toBeNull();
    expect(within(screen.getByLabelText("Grupo de formación")).queryByRole("option", { name: "Pregrado" })).toBeNull();
    fireEvent.change(screen.getByLabelText("Buscar título, institución o municipio"), { target: { value: "Derecho" } });
    expect(screen.queryByRole("list", { name: "Oferta de educación superior" })).toBeNull();
    expect(screen.getByText("Prueba con otros filtros")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Ver todas las instituciones" }));
    expect(screen.getByRole("list", { name: "Oferta de educación superior" })).toBeTruthy();
  });

  it("explora modalidades y niveles con sus activos e inactivos y botones de oferta explícitos", () => {
    render(<ExploradorSuperior detalle={ejemplo()} />);
    fireEvent.click(screen.getByRole("tab", { name: "Modalidades" }));
    const virtual = within(screen.getByRole("list", { name: "Modalidades" })).getByText("Virtual").closest("li")!;
    expect(within(virtual).getByText("6")).toBeTruthy();
    expect(within(virtual).getAllByText("3")).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: "Ver oferta de Virtual" }));
    expect((screen.getByLabelText("Modalidad del programa") as HTMLSelectElement).value).toBe("Virtual");
    expect(screen.getByRole("status").textContent).toContain("1–5 de 6 ofertas publicadas");
    fireEvent.click(screen.getByRole("tab", { name: "Niveles" }));
    fireEvent.click(screen.getByRole("button", { name: "Ver oferta de Maestría" }));
    expect((screen.getByLabelText("Nivel académico de la oferta") as HTMLSelectElement).value).toBe("Maestría");
    expect((screen.getByLabelText("Modalidad del programa") as HTMLSelectElement).value).toBe("");
    expect(screen.getByRole("status").textContent).toContain("1–5 de 5 ofertas publicadas");
  });

  it("conserva la institución al comparar sus modalidades y niveles sin mezclar la oferta de otras", () => {
    render(<ExploradorSuperior detalle={ejemplo()} />);
    fireEvent.click(screen.getByRole("tab", { name: "Instituciones" }));
    fireEvent.click(screen.getByRole("button", { name: "Ver oferta de Instituto tecnológico" }));
    fireEvent.click(screen.getByRole("tab", { name: "Modalidades" }));
    const virtual = within(screen.getByRole("list", { name: "Modalidades" })).getByText("Virtual").closest("li")!;
    expect(within(virtual).getByText("2")).toBeTruthy();
    expect(within(virtual).getAllByText("1")).toHaveLength(2);
    expect(screen.getByText(/Modalidades de la institución seleccionada/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Ver oferta de Virtual" }));
    const oferta = screen.getByRole("list", { name: "Oferta de educación superior" });
    expect(within(oferta).getAllByRole("listitem")).toHaveLength(2);
    expect(within(oferta).getAllByText("Instituto tecnológico")).toHaveLength(2);
    expect(within(oferta).queryByText("Universidad del territorio")).toBeNull();
    expect((screen.getByLabelText("Nivel académico de la oferta") as HTMLSelectElement).options).toHaveLength(2);
    fireEvent.click(screen.getByRole("tab", { name: "Niveles" }));
    expect(screen.getByRole("button", { name: "Ver oferta de Maestría" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Ver oferta de Universitaria" })).toBeNull();
  });

  it("desglosa seis niveles de una institución, limita filtros y distingue pregrado, posgrado y formación desconocida", () => {
    const niveles = ["Universitaria", "Tecnológica", "Especialización universitaria", "Maestría", "Doctorado", "Exterior"];
    const ofertas = niveles.map((nivel, indice) => ({ titulo_obtenido: `Título del nivel ${indice + 1}`, institucion: "Universidad elegida", nivel,
      estado: indice % 2 ? "Inactivo" : "Activo", modalidad: indice % 2 ? "Virtual" : "Presencial" }));
    const detalle: Registro = { lista_oferta: [...ofertas, { titulo_obtenido: "Título de otra institución", institucion: "Otra universidad", nivel: "Formación técnica profesional", estado: "Activo", modalidad: "A distancia" }],
      resumen_oferta: { total_ofertas: 7, unidad_conteo: "ofertas publicadas", instituciones: [
        { institucion: "Universidad elegida", total_ofertas: 6, activos: 3, inactivos: 3, sin_estado: 0,
          ciclos: [{ ciclo: "Pregrado", total: 2, activos: 1, inactivos: 1, sin_estado: 0 },
            { ciclo: "Posgrado", total: 3, activos: 2, inactivos: 1, sin_estado: 0 },
            { ciclo: "Sin información", total: 1, activos: 0, inactivos: 1, sin_estado: 0 }] },
        { institucion: "Otra universidad", total_ofertas: 1, activos: 1, inactivos: 0, sin_estado: 0 },
      ] } };
    render(<ExploradorSuperior detalle={detalle} />);
    fireEvent.click(screen.getByRole("tab", { name: "Instituciones" }));
    fireEvent.click(screen.getByRole("button", { name: "Ver oferta de Universidad elegida" }));
    expect(within(screen.getByLabelText("Modalidad del programa")).queryByRole("option", { name: "A distancia" })).toBeNull();
    expect(within(screen.getByLabelText("Nivel académico de la oferta")).queryByRole("option", { name: "Formación técnica profesional" })).toBeNull();
    fireEvent.click(screen.getByRole("tab", { name: "Niveles" }));
    expect(screen.getByText("Página 1 de 2")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(screen.getByRole("list", { name: "Niveles" }).querySelectorAll("li")).toHaveLength(1);
    fireEvent.click(screen.getByRole("tab", { name: "Formación" }));
    const lista = screen.getByRole("list", { name: "Formación" });
    const pregrado = within(lista).getByText("Pregrado").closest("li")!;
    expect(within(pregrado).getByText("2")).toBeTruthy();
    expect(within(pregrado).getAllByText("1")).toHaveLength(2);
    const desconocida = within(lista).getByText("Formación no informada").closest("li")!;
    expect(within(desconocida).getAllByText("1")).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: "Ver oferta de Posgrado" }));
    expect((screen.getByLabelText("Grupo de formación") as HTMLSelectElement).value).toBe("Posgrado");
    expect(screen.getByRole("list", { name: "Oferta de educación superior" }).querySelectorAll("li")).toHaveLength(3);
    fireEvent.change(screen.getByLabelText("Grupo de formación"), { target: { value: "Maestría" } });
    expect(screen.getByRole("list", { name: "Oferta de educación superior" }).querySelectorAll("li")).toHaveLength(1);
    expect(screen.getByText("Título del nivel 4")).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Formación" }));
    fireEvent.click(screen.getByRole("button", { name: "Ver oferta de Formación no informada" }));
    expect(screen.getByRole("list", { name: "Oferta de educación superior" }).querySelectorAll("li")).toHaveLength(1);
    expect(screen.getByText("Título del nivel 6")).toBeTruthy();
  });

  it("mantiene todas las instituciones, admite búsqueda sin tildes y navegación de pestañas con teclado", () => {
    const detalle = ejemplo();
    (detalle.resumen_oferta as Registro).instituciones = Array.from({ length: 41 }, (_, indice) => ({
      institucion: `Institución ${indice + 1}`, total_ofertas: indice + 1, activos: indice + 1, inactivos: 0, sin_estado: 0,
    }));
    render(<ExploradorSuperior detalle={detalle} />);
    const ofertaTab = screen.getByRole("tab", { name: "Programas y títulos" });
    fireEvent.keyDown(ofertaTab, { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "Instituciones" }).getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(screen.getByRole("tab", { name: "Instituciones" }));
    fireEvent.change(screen.getByLabelText("Ir a la página"), { target: { value: "9" } });
    expect(screen.getByRole("button", { name: "Ver oferta de Institución 41" })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Buscar institución"), { target: { value: "institucion 12" } });
    expect(screen.getByRole("button", { name: "Ver oferta de Institución 12" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Siguiente" })).toBeNull();
  });

  it("abre el detalle completo e informa solo las consultas realmente parciales", () => {
    Object.defineProperty(HTMLDialogElement.prototype, "showModal", { configurable: true, value: function(this: HTMLDialogElement) { this.setAttribute("open", ""); } });
    Object.defineProperty(HTMLDialogElement.prototype, "close", { configurable: true, value: function(this: HTMLDialogElement) { this.removeAttribute("open"); } });
    const detalle = ejemplo(); detalle.consulta_completa = false;
    render(<ExploradorSuperior detalle={detalle} />);
    fireEvent.click(screen.getByRole("button", { name: "Ver detalle de Título 1 en Universidad del territorio" }));
    const dialogo = screen.getByRole("dialog", { name: "Detalle de la oferta educativa" });
    expect(within(dialogo).getByText("Villavicencio")).toBeTruthy();
    expect(within(dialogo).getByText("Modalidad")).toBeTruthy();
    expect(within(dialogo).getByText("Virtual")).toBeTruthy();
    fireEvent.click(within(dialogo).getByRole("button", { name: "Cerrar" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByText(/incluye una parte de la oferta disponible/)).toBeTruthy();
  });
});
