# Backend Python de EducaDatos

El backend es el servicio que recibe una pregunta, consulta las fuentes públicas
y devuelve datos, fuentes y advertencias a la página web. Está implementado con
Python y FastAPI dentro del repositorio principal. No requiere registro ni claves
de IA para consultar datos educativos.

La interpretación de preguntas usa reglas de enrutamiento hacia los servicios
especializados. No incorpora un modelo de IA generativa ni inventa respuestas
cuando falla una fuente. Los diagnósticos y las agrupaciones son exploratorios.

## Archivos principales

| Archivo | Qué hace |
| --- | --- |
| `main.py` | Arranca la API y sus rutas generales. |
| `models/schemas.py` | Valida preguntas, territorios y límites; define la respuesta común. |
| `services/router_api.py` | Consultas estructuradas para la web y el backend reconstruido. |
| `services/adaptador_api.py` | Conserva y presenta datos, fuentes, advertencias y respuesta ciudadana. |
| `services/consulta_service.py` | Identifica qué servicio necesita cada pregunta. |
| `services/*_service.py` | Consulta colegios, programas, bachilleres, ICETEX y análisis territoriales. |
| `utils/cache_datos.py` | Reutiliza datos descargados durante un tiempo limitado. |

## Arrancarlo en tu Mac, paso a paso

Estos pasos ejecutan el backend en tu propio equipo. No requieren Cloud Run.

1. Abre Terminal y entra en tu copia del proyecto:

   ```bash
   cd /Users/danielcontreras/Documents/EducaDatos_Git
   git status
   ```

   Si tienes cambios propios, conserva una copia antes de actualizar. Con el
   checkout sin cambios pendientes, trae la versión publicada:

   ```bash
   git pull --ff-only origin main
   ```

2. Comprueba Python:

   ```bash
   python3.11 --version
   ```

   Se validó Python **3.11.16**. Si aparece `command not found` y tienes Homebrew,
   puedes instalar la rama 3.11 con `brew install python@3.11`. Si no tienes ese
   gestor, sus instrucciones para Mac están en [brew.sh](https://brew.sh/).
   Después vuelve a comprobar `python3.11 --version`.

3. Crea un entorno virtual. Es una carpeta para las dependencias de este proyecto:

   ```bash
   python3.11 -m venv .venv
   ```

4. Instala las dependencias del backend y las herramientas de prueba:

   ```bash
   .venv/bin/python -m pip install --require-hashes -r requirements-dev.lock
   ```

   La primera instalación necesita conexión a Internet. Las versiones y hashes
   están fijados para que puedas repetirla. La verificación en esta tarea fue
   en Linux con Python 3.11; la instalación de macOS debe comprobarse en tu equipo.

5. Arranca el backend:

   ```bash
   OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 .venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
   ```

   Espera a ver `Application startup complete`. Mantén esa Terminal abierta.
   Para detener ese servicio, pulsa **Control + C** en esa misma ventana.

6. En tu navegador, escribe `http://127.0.0.1:8000/docs`. Es la documentación
   interactiva de tu backend local. Busca **POST /chat**, pulsa **Try it out**,
   escribe este cuerpo y pulsa **Execute**:

   ```json
   { "pregunta": "Hola" }
   ```

   Debes recibir código **200** y una respuesta de EducaDatos. Después prueba:

   ```json
   { "pregunta": "¿Cuántos colegios oficiales y privados hay en Soacha?" }
   ```

   La primera descarga de una fuente puede tardar. Las respuestas deben mostrar
   fuentes y advertencias; una fuente que no responde genera un error visible.

7. Para conectar la web, abre una **segunda Terminal** en la misma carpeta:

   ```bash
   cd /Users/danielcontreras/Documents/EducaDatos_Git
   npm ci --prefix web
   npm run dev --prefix web
   ```

   Necesita Node.js 22.12 o posterior; se validó Node.js 24. Abre en tu navegador
   la dirección que muestre Vite. Sin URL pública configurada en `.env.local`,
   la web conecta `/api` con el backend local en el puerto 8000.

## Consultas disponibles

### Código DANE y orientación

`POST /colegios/codigo-dane` recibe un nombre o código, y opcionalmente departamento
y municipio. Sin territorio busca a nivel nacional, siempre en la vigencia más
reciente del MEN. La misma consulta está disponible por `/chat`, por ejemplo:

```json
{"pregunta":"Código DANE del colegio \"Academia Militar José Antonio Páez\" en Villavicencio"}
```

`ConsultaDaneRequest` valida longitudes, nombres y códigos antes de consultar.
Las búsquedas por nombre usan filtros SoQL construidos con identificadores fijos,
valores escapados y sustitución de tildes. Si hay varios colegios con el mismo
nombre, muestra municipio y departamento sin elegir arbitrariamente. Si falta
el código no lo inventa. El código identifica un establecimiento y no necesariamente
cada una de sus sedes.

`services/orientacion_service.py` identifica peticiones de opinión, argumentación,
ideología y causalidad mediante reglas explícitas. Responde con el alcance de
EducaDatos y preguntas informativas sugeridas, sin descargar datos para justificar
opiniones. Las explicaciones descriptivas de datos y los indicadores conservan
sus rutas. No es un clasificador semántico universal: los nombres breves que no
son indicadores pueden tratarse como posibles títulos para buscar a nivel nacional.

### Presentación ciudadana y oferta de educación superior

`services/presentacion_service.py` prepara colecciones con `titulo`, `filas` y
`es_muestra`, conservando las evidencias y campos técnicos en el contrato API.
La interfaz usa cinco filas por página y un panel fijo. Los códigos y años nunca
se formatean como cantidades. Los resúmenes o muestras siguen identificados como
tales, incluso cuando tienen varias páginas.

El servicio de educación superior busca en nombres fiables, títulos otorgados
e instituciones. Conserva el nombre completo consultado, compara palabras sin
tildes y relaciona nombres habituales (por ejemplo, Arquitectura → ARQUITECTO e
Ingeniería → INGENIERO) con los títulos publicados. No usa coincidencias del área
general de conocimiento para afirmar que una institución ofrece un programa
específico. Sin territorio la búsqueda es nacional; por ciudad/departamento usa
los campos territoriales de la oferta reportada. La ruta estructurada admite
`estado: "Activo"` o `"Inactivo"`.

`lista_oferta` conserva títulos, institución, estado, nivel, territorio y modalidad.
La deduplicación usa esos campos juntos: el mismo título en otra institución,
ciudad, nivel, modalidad o estado conserva su entrada. `muestra_programas` continúa
como campo de compatibilidad, pero no limita el nuevo listado a diez filas.
Si la descarga alcanza su límite, la respuesta marca que puede ser parcial.

La fuente upr9-nkiz sigue teniendo nombres y códigos de programas inconsistentes.
El conteo de programas únicos permanece en null; la respuesta principal se centra
en los títulos e instituciones y las distribuciones de estados/niveles. La advertencia
no se elimina ni se convierte un título en un identificador de programa. El estado
es el reportado por la fuente y no certifica aperturas de convocatoria o disponibilidad
actual de matrículas. Una institución de educación superior no necesariamente es
una universidad; se conserva el nombre y tipo de registro publicados.

### Colegios: última vigencia y directorio completo

`services/directorio_colegios.py` consulta `max(a_o)` en el dataset oficial del MEN
`cfw5-qzt5`, después cuenta y descarga los registros del territorio **de esa
vigencia**, por páginas de hasta 5000 filas ordenadas por el identificador de
Socrata. Usa filtros exactos de municipio/departamento, sin la búsqueda general
`$q`. Si el territorio no tiene registros de ese año, informa la ausencia sin
volver silenciosamente a un año anterior.

El código DANE identifica cada colegio; si falta, se usa el nombre normalizado
con su territorio y se informa esta limitación. El conteo y la distribución por
sector salen de la misma lista sin duplicados. Dos códigos DANE diferentes
identifican colegios diferentes aunque sus nombres coincidan. Si el código DANE
tiene sectores contradictorios, su tipo se muestra como «Sin dato».

En este directorio, `limit` se conserva por compatibilidad con la API y se reporta
como `limit_solicitado`; no recorta la lista ni convierte una muestra en un total.
`limit_usado` indica las filas descargadas. El máximo `MAX_LIMIT` limita el tamaño
total aceptado: si se supera o una página falla, se informa un error de fuente
(502), en vez de presentar un directorio parcial como completo. Las consultas
usan la caché común con su caducidad configurada (3600 segundos por defecto).

`colegios en villavicencio` pide una lista. `¿Cuántos colegios hay en Villavicencio?`
pide un conteo. Pedir «públicos y privados» mantiene ambos sectores; pedir uno
aplica el filtro antes de obtener el conteo. La interfaz ofrece los tres filtros
como botones sin requerir otra pregunta escrita.

La vigencia publicada puede ser anterior al año actual. La aplicación informa
el año disponible y no certifica el estado presente de cada colegio.

Todas estas rutas aceptan JSON mediante **POST** y devuelven el contrato común:

| Ruta | Datos de entrada principales |
| --- | --- |
| `/chat` | `pregunta`, `limit` opcional. |
| `/colegios` | Departamento o municipio; `sector` y `modo_respuesta` opcionales. |
| `/programas-superior` | Departamento, municipio o búsqueda por `texto`. |
| `/bachilleres` | Departamento o municipio. |
| `/icetex` | Departamento opcional (nacional por defecto); `tipo`, `anio` y `filtros` opcionales. |
| `/transito-educativo` | Departamento o municipio. |
| `/diagnostico-municipal` | Departamento o municipio; también permite diagnóstico departamental. |
| `/cluster-municipal` | Departamento y municipio. |
| `/similar` | Departamento y municipio. |
| `/recomendaciones` | Departamento y municipio. |

Las consultas estructuradas aceptan `limit`, acotado por `MAX_LIMIT`. Los servicios
mantienen mínimos amplios cuando necesitan evitar muestras territoriales parciales;
pedir un límite pequeño no garantiza que la descarga sea pequeña. Para colegios,
`modo_respuesta` es `conteo` o `lista`. Un sector desconocido se rechaza.

Se mantienen las rutas GET anteriores y `/ciudadano/*` para compatibilidad.
`/ciudadano/*` conserva sus respuestas técnicas; las rutas de la tabla usan el
formato común de la web.

## Qué recibe la web

```json
{
  "pregunta": "Pregunta del visitante",
  "respuesta": "Texto explicado para el ciudadano",
  "datos": {},
  "fuentes": [],
  "advertencias": [],
  "respuesta_ciudadana": {}
}
```

`respuesta_ciudadana` añade compatibilidad con la interfaz del ZIP reconstruido.
La web actual sigue leyendo los cinco campos anteriores. En `datos`,
`detalle_consulta` contiene los indicadores disponibles. Un conteo `null` significa
**No disponible**, no cero.

Los códigos de error son 422 para entrada inválida, 404 para un municipio no
encontrado en el análisis de grupos, 502 para fallo de fuente y 503 para sobrecarga.
El 503 incluye `Retry-After`. Un análisis parcial incluye sus advertencias y los
componentes no disponibles; no elimina esas limitaciones de la respuesta pública.

## Comprobar el backend

Desde la raíz, con el entorno instalado:

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check --select F821,F811,E9,F401 .
```

Para consultas reales, con el backend encendido:

```bash
EDUCADATOS_BASE_URL=http://127.0.0.1:8000 .venv/bin/python probar_backend.py
```

Este último comando consulta fuentes externas y puede tardar varios minutos.
Su salida y código de retorno indican si hubo fallos. No convierte una respuesta
de error con HTTP 200 en una prueba satisfactoria.

Primero comprueba Python y la web local. Después podrás seguir
[la guía de publicación](PUBLICAR.md) para llevarlos a un servicio público.

## Precisión de las estadísticas de ICETEX

`services/estadisticas_icetex.py` usa los campos verificados de `26bn-e42j` y
`nvcf-b8a3`. Calcula sumas mediante SoQL en la fuente completa, agrupadas por año y
por cada dimensión; no estima beneficiarios contando las filas de una muestra.
Otorgados suma `numero_de_nuevos_beneficiarios`; renovados suma
`numero_de_renovaciones`. Se conserva el campo heredado
`total_creditos_o_beneficiarios_aproximado` para compatibilidad, pero la presentación
usa la unidad explícita de `visualizacion_icetex`. Un cero válido se mantiene;
una cobertura no disponible devuelve `null`.

Cada agregado comprueba cantidades enteras no negativas y que todos los registros
del año tengan cantidad informada. Todas las distribuciones deben sumar el mismo
total. Una discrepancia, un agregado truncado o una cantidad inválida produce
error de fuente (502), sin publicar un total parcial. Máximo cuatro solicitudes
concurrentes por análisis, utilizando la caché y TLS existentes. No se descarga
el historial fila por fila; `limit` permanece como entrada compatible y no limita
las sumas oficiales.

La fuente permite **departamento de origen**, no ciudad ni institución por nombre.
Una consulta municipal no se sustituye silenciosamente por el departamento.
La palabra Colombia como ámbito nacional se distingue del municipio Colombia,
Huila. Los códigos de rango de desembolso no tienen montos exactos disponibles
para convertirlos en pesos. La fecha más reciente corresponde al reporte
publicado y no certifica que el año esté completo.

`POST /icetex` admite `anio` (1900–2100), `tipo` otorgados/renovados y `filtros` con
claves cerradas: `nivel_de_formacion`, `modalidad_de_linea`, `modalidad_del_credito`,
`sector_ies`, `sexo_al_nacer`, `estrato_socio_economico`,
`categoria_del_municipio_de` y `rango_del_valor_total`. Valores escapados,
identificadores fijos y estrato numérico validado evitan instrucciones SoQL
provenientes de la entrada. El chat reconoce filtros frecuentes explícitos como
pregrado, posgrado en Colombia, exterior, sexo, estrato, sector, destino del
crédito, maestría y doctorado. No es una comprensión universal del lenguaje:
si se nombran varios valores del mismo campo, se presenta la distribución sin
elegir arbitrariamente uno de ellos.

`visualizacion_icetex` incluye unidad, explicación, total, año, cobertura,
serie anual y diez distribuciones con notas legibles. La comparación de otorgados
y renovados utiliza `comparacion_icetex` y nunca suma sus unidades.
`resumenes_icetex` conserva estos paneles en consultas integradas; sus lecturas
usan nuevos beneficiarios y renovaciones, y no presentan cobertura municipal
inexistente como datos encontrados.
