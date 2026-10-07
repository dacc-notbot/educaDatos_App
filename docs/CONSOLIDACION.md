# Consolidación y recuperación

Origen principal: `dacc-notbot/educaDatos_App`, HEAD inicial
`c303cc78b50a92f223e207452bb0f5fa028a27c2`.

Origen de respaldo: `dacc-notbot/-EduDatos_Colombia_AI`, HEAD inicial
`3541304c09d3f18eaf3ebe7d6de0be77209dc2a1`.

Los dos checkouts estaban limpios antes de los cambios. Se crearon archivos
completos que incluyen `.git` y se verificó el hash de cada archivo recuperable:

- `/workspace/backups/originales/educaDatos_App.tar.gz`
- `/workspace/backups/originales/-EduDatos_Colombia_AI.tar.gz`

Las sincronizaciones posteriores guardan otro archivo verificado bajo
`/workspace/backups/versiones`. Para recuperar, extrae en un directorio nuevo y
comprueba sus archivos e historial; no extraigas encima de cambios actuales.

`main_respaldo.py` era una implementación anterior con imports hacia los servicios
ausentes y funciones duplicadas para colegios, diagnóstico, normalización y
consultas Socrata. Se conserva en el archivo original del segundo repositorio.
La aplicación activa usa los servicios especializados completos del principal.
`pyvenv.cfg` apuntaba a una instalación de macOS y se retiró de la copia activa.

Cambios funcionales:

- Configuración por variables y `.env`, una sola versión y modelos compartidos.
- Conversión numérica que conserva los decimales entregados por Socrata.
- Conteo especializado de colegios con filtro de sector.
- Programas contados por código, con la ubicación del programa como prioridad
  sobre la dirección principal de la institución; selección determinista de columnas.
- Detección de la columna `a_o` para no mezclar vigencias en clustering.
- Registro del router ciudadano existente y errores HTTP de fuente externa.
- Caché de datos con vencimiento, límite de entradas y escritura atómica.
- Caché territorial que distingue el límite de consulta y modelos con vencimiento.
- Dependencias fijadas y verificadas con hashes, sin requerir ngrok.
- Runner de integración con código de salida correcto y detección de fallback.
- Pruebas de regresión y sincronización de respaldo con protección de cambios.

El acceso a los 12 datasets públicos se comprobó con solicitudes HTTPS reales.
En `upr9-nkiz` se detectó que `nombreprograma` y `codigoprograma` contienen
nombres y códigos de departamentos. La aplicación señala esta inconsistencia,
deja el conteo de programas como no disponible y muestra títulos e instituciones
con sus etiquetas reales. No presenta departamentos ni títulos como programas únicos.
La configuración de red del entorno estaba en modo `unrestricted`; no fue
necesario ampliar de nuevo los permisos. No se desactivó verificación TLS.

Los remotos Git conservan sus identidades originales. La sincronización copia el
código entre checkouts; los commits y pushes se realizan por separado. El servicio
aún no se ha desplegado desde esta configuración. La copia de respaldo es el
mismo proyecto, con su historial Git original.
