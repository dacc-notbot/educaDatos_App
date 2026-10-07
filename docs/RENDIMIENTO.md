# Optimización de consultas

El diagnóstico departamental recorría y normalizaba todos los campos de cada fila
aunque existieran columnas explícitas de departamento y municipio. Además,
consultaba programas dos veces en el mismo diagnóstico.

Se conserva el filtro textual de respaldo cuando faltan columnas, incluida la
coincidencia por secretaría de bachilleres. Los filtros con columnas conocidas
solo normalizan los valores necesarios. La normalización de etiquetas cortas se
reutiliza con un máximo de 8192 entradas y 256 caracteres por etiqueta; las filas
completas no se retienen en esa caché. El tránsito educativo reutiliza la consulta
de programas realizada por el mismo diagnóstico, con territorio y límites iguales.

La caché coordina únicamente descargas idénticas. Una fuente que tarda en responder
no bloquea consultas distintas ni lecturas de datos disponibles. Los bloqueos se
retiran al terminar; no se conserva un registro creciente de claves consultadas.

## Medición

Se ejecutó `diagnostico_territorial_educativo_service(departamento="Cundinamarca",
limit=1000)` antes y después, en procesos nuevos, con los mismos datos públicos ya
descargados en la caché de archivos:

| Estado | Duración |
| --- | ---: |
| Antes | 81,288 s |
| Después | 3,468 s |

El resultado JSON completo fue idéntico. La mejora es de aproximadamente 23 veces
para esta consulta, con una reducción de tiempo del 95,7 %. La primera descarga
de datos sigue dependiendo del tamaño de la fuente y su conectividad: esta medición
no representa la latencia de una instancia sin datos descargados.

La verificación final pasó 45 pruebas automáticas y las 44 consultas del runner
real (14 rutas y 30 preguntas de chat). Una ejecución anterior registró un timeout
de datos.gov.co al consultar colegios de Soacha; la fuente volvió a responder y
la ejecución final pasó. Estos resultados no garantizan la disponibilidad de la
fuente oficial ni sustituyen una prueba de carga del despliegue público.

## Control de carga

`MAX_CONCURRENT_ANALYSES=2` limita las peticiones analíticas simultáneas por proceso.
Al superar el límite, la API responde 503 con `Retry-After: 3`, sin acumular otra
consulta costosa en espera. Salud, catálogo estático, documentación y preflight
CORS siguen disponibles. Las respuestas de sobrecarga incluyen CORS para que
una web en otro dominio pueda mostrar el mensaje y el tiempo de reintento.

Esta limitación no reemplaza el máximo de instancias, presupuesto ni supervisión
que deben configurarse al desplegar en Cloud Run. La web debe mostrar el estado
ocupado y permitir reintentar; no debe reenviar solicitudes en un bucle inmediato.
