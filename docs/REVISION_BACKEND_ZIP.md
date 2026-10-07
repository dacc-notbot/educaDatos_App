# Revisión de EducaDatos_reconstruido_completo.zip

El archivo recibido se conservó sin modificar y se extrajo fuera de los checkouts
para compararlo con el proyecto principal. Sus instrucciones de instalación se
trataron como documentación del paquete; la tarea autorizada fue analizar y
adaptar el backend, conservando el proyecto existente.

SHA-256 del ZIP:
`09471db481345f3b739a8c97c8d70a476e193f5b313ef68f5881fa24d49d0b9f`.

## Hallazgos

| Componente del ZIP | Hallazgo | Decisión |
| --- | --- | --- |
| Extracción de fuentes y advertencias | Recupera información dentro de `resultados` que el adaptador principal podía omitir. | Integrar y ampliar a componentes de diagnósticos y cruces, sin recorrer filas de datos. |
| `respuesta_ciudadana` | La interfaz adjunta usa la respuesta estructurada. | Añadir el campo conservando el contrato de la web actual. |
| Rutas POST | Propone `/colegios`, `/similar`, `/recomendaciones` y `/transito-educativo`. | Implementarlas mediante los servicios completos existentes y sumar bachilleres, programas e ICETEX. |
| Modelos | Permiten límites sin máximo y territorios vacíos. | Validar territorios, longitud, sectores, tipos de crédito y límites antes de consultar. |
| Conversión numérica | Elimina todos los puntos: `56.11` se convierte en `5611`. | Mantener el conversor verificado del principal. |
| Bachilleres e ICETEX | Suma registros sin seleccionar una vigencia comparable; puede usar dinero o filas como sustituto de beneficiarios. | Conservar la detección de columnas y vigencia de los servicios actuales. |
| Programas | No detecta que `nombreprograma` reproduce departamentos en la fuente comprobada. | Conservar advertencia, títulos reportados y conteo de programas en `null`. |
| Clustering | No reconoce `a_o` y puede incluir códigos territoriales en los indicadores numéricos. | Conservar selección de variables, año y normalización del principal. |
| Territorios | Usa un diccionario fijo de municipios frecuentes y coincidencias por subcadena. | Mantener el catálogo nacional y coincidencias de frases completas. |
| Configuración | Fija un dominio temporal de ngrok y usa CORS con credenciales y origen comodín. | Mantener configuración por entorno y acceso público sin credenciales. |
| Pruebas del ZIP | Son reducidas frente al runner y las regresiones existentes. | Mantenerlas y añadir casos de compatibilidad y errores. |

También se corrigió una ruta del principal: `/cluster-municipal` devolvía HTTP 200
cuando fallaba el servicio. Ahora devuelve 404 o 502 según el motivo, en lugar de
presentar una consulta fallida como éxito.

## Fuente adicional encontrada

El ZIP declara `resultados_saber_pro` (`u37r-hjmu`). Se verificó su metadata y una
fila por HTTPS: la fuente se titula **Resultados únicos Saber Pro** y describe
resultados anonimizados de **2018 a 2022**. El ZIP no implementa un servicio de
análisis específico ni su enrutamiento ciudadano.

No se mezcló esa fuente histórica con los diagnósticos actuales. Un módulo futuro
de Saber Pro debe definir periodo, ubicación del programa frente a residencia y
agregación de puntajes antes de presentar indicadores. El catálogo activo conserva
las 12 fuentes y las series ya utilizadas por los servicios verificados.

## Resultado de la adaptación

El proyecto conserva un único backend Python, configuración, cachés, dependencias
fijadas y servicios especializados. Las rutas nuevas están separadas en
`services/router_api.py`; la adaptación pública está en `services/adaptador_api.py`.
No se reemplazó la web ni se introdujo una segunda implementación.

Las pruebas automatizadas comprueban recuperación de fuentes, advertencias
anidadas, fallos parciales, conteos `null`, validación y límites, compatibilidad
de rutas y errores HTTP. La ejecución local y las consultas reales se verifican
antes de publicar los cambios. Cloud Run queda pendiente hasta que el usuario
compruebe el backend y la web en su equipo.

Validación de esta adaptación: 75 pruebas Python, 9 pruebas de la web,
compilación TypeScript/Vite y análisis estático pasaron. Las diez rutas POST de
la tabla de `BACKEND.md` respondieron correctamente con consultas reales;
se verificaron además las fuentes de similitud y recomendaciones tras completar
su adaptación. Chromium comprobó una pregunta real sobre colegios privados de
Soacha desde la web móvil, con fuentes, advertencias y sin errores de JavaScript.
Las primeras consultas reales tardaron hasta unos 21 segundos en esta instancia;
la conectividad y disponibilidad de datos.gov.co siguen siendo externas.
