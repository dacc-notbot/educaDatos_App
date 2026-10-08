import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import SelectorTerritorio from "./SelectorTerritorio";
import type { TerritorioSeleccionado } from "./SelectorTerritorio";

const catalogo = {
  fuente: "MEN", anio: 2024,
  departamentos: [
    { departamento: "Antioquia", municipios: [{ municipio: "Granada", codigo: "05313" }, { municipio: "Medellín", codigo: "05001" }] },
    { departamento: "Bogotá, D.C.", municipios: [{ municipio: "Bogotá, D.C.", codigo: "11001" }] },
    { departamento: "Meta", municipios: [{ municipio: "Acacías", codigo: "50006" }, { municipio: "Granada", codigo: "50313" }, { municipio: "Villavicencio", codigo: "50001" }] },
  ],
};
function respuesta() { return new Response(JSON.stringify(catalogo), { status: 200 }); }
function Contenedor({ inicial = {} }: { inicial?: TerritorioSeleccionado }) {
  const [valor, setValor] = useState(inicial);
  const [valido, setValido] = useState(false);
  return <><SelectorTerritorio valor={valor} onChange={setValor} onValidezChange={setValido} /><output aria-label="Selección">{JSON.stringify(valor)}</output><button disabled={!valido}>Buscar</button></>;
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it("limita las opciones al departamento y permite recorrer sus municipios sin cambiar a nacional", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respuesta()));
  render(<Contenedor inicial={{ departamento: "Meta" }} />);
  await waitFor(() => expect((screen.getByRole("combobox", { name: "Municipio" }) as HTMLInputElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole("button", { name: "Ver los 3 municipios de Meta" }));
  expect(screen.getByRole("option", { name: "Villavicencio · Meta" })).toBeTruthy();
  expect(screen.getByRole("option", { name: "Granada · Meta" })).toBeTruthy();
  expect(screen.queryByRole("option", { name: "Medellín · Antioquia" })).toBeNull();
  fireEvent.click(screen.getByRole("option", { name: "Villavicencio · Meta" }));
  expect(screen.getByText("Villavicencio pertenece a Meta.")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Todo Meta" }));
  expect(screen.getByLabelText("Selección").textContent).toBe('{"departamento":"Meta"}');
});

it("identifica el departamento al escribir una ciudad nacional y mantiene todos los municipios vecinos", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respuesta()));
  render(<Contenedor />);
  await screen.findByText("Buscarás en toda Colombia.");
  await waitFor(() => expect((screen.getByRole("button", { name: "Buscar" }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.change(screen.getByRole("combobox", { name: "Municipio" }), { target: { value: "villavicencio" } });
  expect(screen.getByLabelText("Selección").textContent).toBe('{"departamento":"Meta","municipio":"Villavicencio"}');
  fireEvent.focus(screen.getByRole("combobox", { name: "Municipio" }));
  expect(screen.getByRole("option", { name: "Acacías · Meta" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Toda Colombia" }));
  expect(screen.getByLabelText("Selección").textContent).toBe("{}");
});

it("mantiene los homónimos y exige escoger el departamento sin aceptar texto incompleto", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respuesta()));
  render(<Contenedor />);
  await waitFor(() => expect((screen.getByRole("button", { name: "Buscar" }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.change(screen.getByRole("combobox", { name: "Municipio" }), { target: { value: "Granada" } });
  expect((screen.getByRole("button", { name: "Buscar" }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByRole("option", { name: "Granada · Antioquia" })).toBeTruthy();
  expect(screen.getByRole("option", { name: "Granada · Meta" })).toBeTruthy();
  expect(screen.getByLabelText("Selección").textContent).toBe("{}");
  fireEvent.keyDown(screen.getByRole("combobox", { name: "Municipio" }), { key: "ArrowDown" });
  fireEvent.keyDown(screen.getByRole("combobox", { name: "Municipio" }), { key: "Enter" });
  expect(screen.getByLabelText("Selección").textContent).toBe('{"departamento":"Meta","municipio":"Granada"}');
  expect((screen.getByRole("button", { name: "Buscar" }) as HTMLButtonElement).disabled).toBe(false);
  fireEvent.change(screen.getByRole("combobox", { name: "Municipio" }), { target: { value: "No existe" } });
  expect(screen.getByLabelText("Selección").textContent).toBe('{"departamento":"Meta"}');
  expect((screen.getByRole("button", { name: "Buscar" }) as HTMLButtonElement).disabled).toBe(true);
});

it("reconoce Bogotá sin puntuación y permite corregir un error sin una lista vacía falsa", async () => {
  const fetchMock = vi.fn().mockResolvedValueOnce(new Response("", { status: 502 })).mockResolvedValueOnce(respuesta());
  vi.stubGlobal("fetch", fetchMock);
  render(<Contenedor />);
  await screen.findByRole("alert");
  expect((screen.getByRole("button", { name: "Buscar" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Reintentar municipios" }));
  await waitFor(() => expect((screen.getByRole("button", { name: "Buscar" }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.change(screen.getByRole("combobox", { name: "Municipio" }), { target: { value: "bogota" } });
  expect(screen.getByLabelText("Selección").textContent).toBe('{"departamento":"Bogotá, D.C.","municipio":"Bogotá, D.C."}');
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

it("aborta la carga al desmontar y no emite un catálogo incompleto", async () => {
  const fetchMock = vi.fn().mockImplementation(() => new Promise(() => {}));
  vi.stubGlobal("fetch", fetchMock);
  const { unmount } = render(<Contenedor />);
  const signal = fetchMock.mock.calls[0][1].signal as AbortSignal;
  expect(signal.aborted).toBe(false);
  unmount();
  expect(signal.aborted).toBe(true);
});

it("valida los cambios de ubicación recibidos desde otra consulta y conserva la edición pendiente", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respuesta()));
  const onChange = vi.fn();
  const onValidezChange = vi.fn();
  const { rerender } = render(<SelectorTerritorio valor={{ departamento: "Meta" }} onChange={onChange} onValidezChange={onValidezChange} />);
  await waitFor(() => expect(onValidezChange).toHaveBeenLastCalledWith(true));
  rerender(<SelectorTerritorio valor={{ municipio: "Villavicencio" }} onChange={onChange} onValidezChange={onValidezChange} />);
  await waitFor(() => expect(onChange).toHaveBeenLastCalledWith({ departamento: "Meta", municipio: "Villavicencio" }));
  rerender(<SelectorTerritorio valor={{ departamento: "Meta", municipio: "Ciudad que no existe" }} onChange={onChange} onValidezChange={onValidezChange} />);
  await waitFor(() => expect(onValidezChange).toHaveBeenLastCalledWith(false));
  expect((screen.getByRole("combobox", { name: "Municipio" }) as HTMLInputElement).value).toBe("Ciudad que no existe");
});
