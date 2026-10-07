# EducaDatos

API pública de datos educativos de Colombia con consultas ciudadanas, diagnósticos
territoriales y agrupación exploratoria de municipios. No requiere registro ni
claves para consultar los conjuntos públicos de datos.gov.co.

## Un único proyecto

- **Principal:** `dacc-notbot/educaDatos_App`. Aquí se desarrolla y se prueba.
- **Respaldo:** `dacc-notbot/-EduDatos_Colombia_AI`. Recibe copias verificadas del
  principal; no se mantiene una segunda implementación.

`main.py` y las dependencias eran idénticos en ambos repositorios. Se conserva la
implementación completa de `educaDatos_App`, incluidos los servicios que faltaban
en el otro checkout. La configuración antigua de ngrok y `main_respaldo.py` se
preservan en los archivos de recuperación, no forman parte del flujo activo.

## Desarrollo local

Requiere Python 3.11. La versión validada es 3.11.16.

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock
[ -e .env ] || cp .env.example .env
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 .venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

En el entorno cloud ya preparado, usa el intérprete
`/workspace/.cloud-onboarding/venvs/educaDatos_App/bin/python`; no hace falta crear
otro entorno virtual. Cada tarea ya está aislada: utiliza los checkouts existentes,
sin crear worktrees. Los procesos se arrancan de nuevo después de restaurar una tarea.

## Configuración

Las variables del proceso tienen prioridad sobre `.env`. Usa `.env.example` como
referencia y no guardes secretos en Git.

- `PUBLIC_BASE_URL`: URL definitiva del backend; por defecto, desarrollo local.
- `CORS_ORIGINS`: orígenes separados por comas; al lanzar la web, establece su dominio.
- `REQUEST_TIMEOUT`: tiempo de espera de la fuente en segundos.
- `CACHE_TTL_SECONDS`: vigencia de datos descargados; `0` desactiva la caché.
- `CACHE_MAX_ENTRIES`: máximo de consultas retenidas en la caché.
- `MAX_CONCURRENT_ANALYSES`: máximo de análisis simultáneos por proceso (2 por
  defecto). Bajo carga, la API devuelve 503 y `Retry-After`; salud y documentación
  siguen disponibles. La web debe mostrar la espera y permitir reintentar.
- `EDUCADATOS_CACHE_DIR`: ubicación de la caché; por defecto `/tmp/educadatos-cache`.
- Los límites de consulta también se pueden configurar. Las consultas analíticas
  mantienen mínimos amplios para evitar presentar una muestra parcial como total.

La caché de archivos reutiliza consultas iguales y solo guarda respuestas válidas.
Las cachés de territorios y modelos tienen vencimiento. La de archivos puede
persistir entre procesos si se conserva su directorio; en Cloud Run el disco local
es temporal y no se comparte entre instancias. Un fallo de datos.gov.co sigue siendo
un fallo cuando no existe una entrada vigente: no se inventan resultados.

## Verificación

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check --select F821,F811,E9,F401 .
EDUCADATOS_BASE_URL=http://127.0.0.1:8000 .venv/bin/python probar_backend.py
```

Las pruebas de regresión no necesitan Internet. La última orden requiere el
backend en ejecución y acceso HTTPS a `www.datos.gov.co`; realiza consultas reales
y puede tardar varios minutos. El archivo de resultados incluye tiempos,
advertencias y errores; el proceso devuelve un código distinto de cero si falla.
HTTP 200 con una respuesta de error del chat no cuenta como éxito.

Rutas principales: `/health`, `/datasets`, `/chat`, `/consulta`, `/colegios`,
`/diagnostico/territorial`, `/cluster/municipio`. Los servicios estructurados están
disponibles también en `/ciudadano`. `/docs` describe la API y `/openapi-gpt.json`
genera el esquema con la URL pública configurada.

## Contenedor

```bash
docker build -t educadatos .
docker run --rm -p 8080:8080 --env-file .env educadatos
```

El contenedor usa dependencias fijadas con hashes, un usuario sin privilegios y
el puerto `PORT` (8080 por defecto). Puede desplegarse en Cloud Run con acceso sin
autenticación. Esta consolidación no publica ni despliega la aplicación.
Para el lanzamiento público todavía deben definirse la interfaz web, el dominio,
los límites de tráfico/costos y la supervisión.

## Actualizar el respaldo gradualmente

Desde el checkout principal en cloud:

```bash
python scripts/sincronizar_respaldo.py          # muestra qué cambiaría
python scripts/sincronizar_respaldo.py --apply  # guarda recuperación, copia y verifica
```

El script conserva el remoto y el historial Git del respaldo, excluye `.env` y
archivos ignorados, verifica los bytes de la copia de recuperación antes de
modificarla y rechaza cambios manuales posteriores en los archivos gestionados.
Repetirlo sin cambios no crea otra copia. Las ubicaciones pueden cambiarse con
`--source`, `--destination` y `--archive-dir`.

Las copias locales se guardan fuera de los repositorios, en `/workspace/backups`.
Conserva también una copia externa antes de eliminar el entorno cloud. Las órdenes
de sincronización no hacen commits ni pushes: revisa y publica las actualizaciones
en GitHub cuando corresponda. Véase [la consolidación](docs/CONSOLIDACION.md).

Consulta también [las mediciones de rendimiento](docs/RENDIMIENTO.md) y
[la guía para crear la interfaz pública](docs/INTERFAZ_WEB.md).
