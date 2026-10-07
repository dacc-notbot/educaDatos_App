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
  incluye búsqueda por nombre o código DANE (sin exigir tildes) y páginas de
  cinco entradas en un panel de altura fija. Cambiar de página no alarga el
  documento ni mueve al usuario a otra parte de la pantalla. Los controles
  Anterior, Siguiente e Ir a la página están siempre debajo del mismo panel.
- Pulsar el nombre abre el código DANE en un diálogo accesible. El código se
  presenta como identificador, sin puntos ni separadores de miles. Si falta en
  la fuente, se informa su ausencia. El diálogo conserva la posición de lectura.
- Al pulsar un botón desde un conteo se consulta `POST /colegios` con el territorio
  detectado y `modo_respuesta: lista`. Los cambios de filtro posteriores reutilizan
  ese directorio completo. Un fallo mantiene el conteo y permite reintentar.
- El origen se explica con el nombre del MEN en la misma pantalla. No se muestran
  enlaces al JSON ni una tabla de columnas técnicas para los colegios.
- La vigencia del listado proviene de la API: no se afirma que represente cambios
  ocurridos después del año publicado. Los tipos desconocidos se muestran como
  «Sin dato»; no se les asigna un sector inventado.

### Otras fuentes y educación superior

La respuesta principal contiene el resultado relacionado con la pregunta. Los
pasos internos de descarga y filtrado no se muestran como hallazgos ciudadanos.
Las limitaciones se conservan en «Sobre esta información» y los hallazgos útiles
se pueden desplegar. Las sugerencias son botones que preparan una pregunta
editable; no la envían automáticamente.

`TablaDatos.tsx` presenta las colecciones preparadas por el backend: registros de
bachilleres, instituciones y modalidades frecuentes, municipios
similares, recomendaciones, conectividad y demás registros que ya trae la
respuesta. Solo cambia el contenido de un panel de 360 px, con cinco filas,
búsqueda, salto de página y detalle individual. Una selección permite cambiar
de colección sin apilar varias tablas. Se indica explícitamente cuándo son
muestras o resúmenes; la paginación no transforma una muestra en una lista completa.

Para educación superior se muestran título otorgado, institución, nivel y
estado. `OfertaSuperior.tsx` presenta distribuciones por estado y nivel y un
buscador de programa con ámbito territorial o nacional. La tabla permite filtrar
Activo/Inactivo y nivel académico. No se ocultan ofertas inactivas ni se mezclan
sus estados al quitar repeticiones. Cuando nombres de programa son inconsistentes,
la pantalla explica brevemente que busca por los títulos reportados; el indicador
de programas únicos no se presenta como un número ni como una tarjeta vacía.

Ejemplos: `Arquitectura`, `Ingeniería de Sistemas en Meta`,
`Programa "Diseño Gráfico" en Medellín` o
`Código DANE del colegio "Academia Militar José Antonio Páez" en Villavicencio`.
Las búsquedas por nombre sin territorio se realizan a nivel nacional. Las
coincidencias ambiguas se muestran para que el usuario pueda precisar su elección.

Una pregunta de opinión, argumentación, ideología o explicación causal recibe
una orientación hacia datos publicados y ejemplos de consultas. Las explicaciones
de los registros y los diagnósticos descriptivos siguen disponibles. La detección
usa reglas de texto explícitas, no comprensión generativa de cualquier frase.

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

### ICETEX: cifras, tablas y gráficos

`ResumenIcetex.tsx` muestra un total con su unidad exacta, el año y el departamento
**de origen**. Otorgados = nuevos beneficiarios reportados; renovados = renovaciones,
no personas únicas. Nunca suma estas dos medidas ni los totales de distintas vistas.

El usuario puede elegir **Tabla** o **Gráfico**, año, tipo de datos y una distribución:
nivel de formación, línea de financiación, destino del crédito, sector de la
institución, sexo reportado, estrato, tipo de territorio, departamento de origen o
periodo del año. **Evolución por año** permite comparar los años publicados. Son
cinco categorías por página en el mismo panel fijo. El tamaño de las barras usa
la escala de toda la distribución, conservada al cambiar de página; las tablas
muestran cantidades y porcentajes sobre el total filtrado del año, sin porcentajes
cuando ese total es cero ni en la comparación anual. Los gráficos tienen etiquetas
accesibles y la tabla permite abrir el detalle de cada cifra.

Los rangos de desembolso se muestran exclusivamente en una tabla, acompañados de
su explicación: la fuente publica códigos, no montos exactos en pesos. No se
transforman números romanos en cantidades monetarias. Las consultas por ciudad
informan que no existe ese detalle y sugieren el departamento; no muestran cero
como si no hubiera beneficiarios. Tampoco se inventan universidades a partir del
sector de las instituciones. El último año disponible puede actualizarse y no
garantiza un reporte anual completo.

Ejemplos: `ICETEX en Meta`, `ICETEX de pregrado en Meta`,
`ICETEX para mujeres de estrato 2 en Meta`, `ICETEX renovados en Meta en 2024`,
`ICETEX otorgados y renovados en Meta` e `ICETEX en Colombia`.
La vista inicial corresponde al dato solicitado cuando se reconoce: por sexo,
estrato, periodos, rangos o evolución. Cambiar el año conserva los filtros
expresados en la pregunta. Una comparación
presenta las medidas separadas y permite elegir cuál explorar. Los diagnósticos
que incluyen componentes ICETEX también conservan esta presentación.
