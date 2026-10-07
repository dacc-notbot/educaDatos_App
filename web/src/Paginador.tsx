export const FILAS_POR_PAGINA = 5;

export default function Paginador({ pagina, total, cambiar, nombre = "registros" }: {
  pagina: number; total: number; cambiar: (pagina: number) => void; nombre?: string;
}) {
  const paginas = Math.max(1, Math.ceil(total / FILAS_POR_PAGINA));
  if (paginas <= 1) return null;
  return <nav className="paginas-colegios" aria-label={`Páginas de ${nombre}`}>
    <button type="button" disabled={pagina === 0} onClick={() => cambiar(pagina - 1)}>Anterior</button>
    <span>Página {pagina + 1} de {paginas}</span>
    <button type="button" disabled={pagina + 1 >= paginas} onClick={() => cambiar(pagina + 1)}>Siguiente</button>
    <label className="salto-pagina">Ir a la página
      <input type="number" min={1} max={paginas} value={pagina + 1} onChange={(event) => {
        const numero = Number(event.target.value);
        if (Number.isInteger(numero) && numero >= 1 && numero <= paginas) cambiar(numero - 1);
      }} />
    </label>
  </nav>;
}
