# Interfaz pública sin registro

La interfaz ya está implementada en `web/` dentro del repositorio principal.
Es un único proyecto con una copia de respaldo. Para publicarla, sigue
[la guía de lanzamiento](PUBLICAR.md).

## 1. Arrancar la web existente

Usa Node.js 22.12 o posterior; se validó Node.js 24. Desde `educaDatos_App`:

```bash
npm ci --prefix web
npm run dev --prefix web
```

Es una aplicación React con TypeScript. Su acceso será anónimo: no requiere una
pantalla de registro ni una identidad para consultar esta API.

Las dependencias, la compilación y `.env.local` ya están excluidas de Git.
El contenedor Python excluye `web/` y conserva su flujo independiente de ejecución.

En desarrollo, Vite conecta `/api` con FastAPI en el puerto 8000. También puedes
configurar explícitamente la URL en `web/.env.local`:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Esta URL es pública y no es un secreto. No incluyas claves de servicios ni tokens
en variables `VITE_*`, porque se incorporan al código que descarga el navegador.
Al publicar, cambia la URL por el backend real de Cloud Run.

## 2. Conectar una pregunta

La web llama a `POST /chat` con un objeto JSON:

```ts
export async function consultar(pregunta: string) {
  const base = import.meta.env.VITE_API_BASE_URL.replace(/\/$/, "");
  const response = await fetch(`${base}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pregunta }),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail ?? "No fue posible consultar en este momento.");
  }
  return data; // pregunta, respuesta, datos, fuentes, advertencias
}
```

La aplicación debe desactivar el botón mientras envía una consulta y volver a
activarlo tanto si recibe un resultado como si hay un error. Limita la pregunta
a 2000 caracteres, como hace el backend, y evita enviar mensajes vacíos.

## 3. Pantalla inicial

Incluye una caja de pregunta, botón de consultar y ejemplos que se puedan pulsar:
“¿Qué colegios hay en Soacha?”, “Haz un diagnóstico educativo de Villavicencio” y
“¿Qué créditos ICETEX hay en Meta?”.

Muestra el texto de `respuesta`, los datos relevantes, los nombres de `fuentes` y
`advertencias` visibles. Renderiza el texto como texto de React, sin insertar
HTML crudo. Un conteo `null` se muestra como “No disponible”, nunca como cero.
Presenta el año de los datos cuando venga en la respuesta, sin asumir que es
el año actual. Los años se presentan como `2025`, sin separador de miles.

### Directorio de colegios

La distribución, tipografía, tarjetas e ilustración conservan el diseño inicial.
La paleta usa grises cálidos: fondo `#f7f7f5`, texto `#303234`, botones grafito
`#373b3f`, acento piedra `#73716c` y bordes `#dedfda`. La bandera conserva sus
colores como símbolo de Colombia. Alternativas para explorar después sin cambiar
el diseño: gris neutro (fondo `#f7f7f7`, botón `#333333`) o gris pizarra
(fondo `#f4f5f6`, botón `#364149`). La versión implementada es la de grises cálidos.

- `colegios en villavicencio` muestra directamente el directorio.
- `¿Cuántos colegios hay en Villavicencio?` muestra el número y los botones
  **Conocer públicos**, **Conocer privados** y **Conocerlos todos**.
- Cada entrada presenta únicamente el nombre del colegio y su tipo. La lista
  incluye búsqueda por nombre (sin exigir tildes) y páginas de 25 entradas.
- Al pulsar un botón desde un conteo se consulta `POST /colegios` con el territorio
  detectado y `modo_respuesta: lista`. Los cambios de filtro posteriores reutilizan
  ese directorio completo. Un fallo mantiene el conteo y permite reintentar.
- El origen se explica con el nombre del MEN en la misma pantalla. No se muestran
  enlaces al JSON ni una tabla de columnas técnicas para los colegios.
- La vigencia del listado proviene de la API: no se afirma que represente cambios
  ocurridos después del año publicado. Los tipos desconocidos se muestran como
  «Sin dato»; no se les asigna un sector inventado.

La fuente oficial de programas tiene una inconsistencia de identificación.
La interfaz debe conservar la advertencia del backend y distinguir los títulos
reportados de un conteo de programas únicos.

## 4. Esperas y errores

- 422: pide corregir la entrada.
- 502: informa que la fuente de datos no respondió correctamente.
- 503: muestra que el servicio está ocupado y permite reintentar después del
  tiempo indicado por `Retry-After`; evita reintentos automáticos ilimitados.
- Error de red: conserva la pregunta y permite intentar de nuevo.

Para desarrollo, inicia FastAPI y la web a la vez. Configura `CORS_ORIGINS` con el
origen que muestre Vite. Al publicar la web, incluye su dominio definitivo en
esa variable y configura `PUBLIC_BASE_URL` con la URL pública del backend.

## 5. Comprobar y compilar

Prueba preguntas reales, respuestas vacías, errores, advertencias, visualización
móvil y navegación con teclado. Luego ejecuta:

```bash
npm run build
```

Ejecuta esa orden desde `web/`, o `npm run build --prefix web` desde la raíz.
El resultado estará en `web/dist/`. Firebase ejecuta una comprobación de la URL
HTTPS del backend y su salud antes de compilar y publicar. La interfaz se puede
comprobar localmente; el lanzamiento público necesita un backend en Cloud Run.

Pruebas automatizadas: `npm test --prefix web` desde la raíz. Cubren consulta,
fuentes, advertencias, conteos no disponibles, años, errores, sobrecarga,
directorio, filtros, búsqueda, paginación y recuperación tras fallos.
