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

Todas estas rutas aceptan JSON mediante **POST** y devuelven el contrato común:

| Ruta | Datos de entrada principales |
| --- | --- |
| `/chat` | `pregunta`, `limit` opcional. |
| `/colegios` | Departamento o municipio; `sector` y `modo_respuesta` opcionales. |
| `/programas-superior` | Departamento, municipio o búsqueda por `texto`. |
| `/bachilleres` | Departamento o municipio. |
| `/icetex` | Departamento o municipio; `tipo`: `otorgados` o `renovados`. |
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
