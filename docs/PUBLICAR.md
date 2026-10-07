# Publicar EducaDatos, paso a paso

La web ya está creada en `web/`. Los archivos de Firebase usan `web/dist`, los
workflows usan `main` y el proyecto es `educadatos-3617c`. No necesitas repetir
`firebase init` ni crear otra página. El acceso de los visitantes será sin registro.

Falta publicar el servicio Python en Cloud Run y conectar su dirección con la web.
Firebase Hosting sirve las pantallas; Cloud Run procesa las preguntas. Ambos
forman parte del mismo proyecto de Google Cloud/Firebase.

## 1. Tener la versión actual en tu Mac

Abre Terminal. Si ya clonaste el proyecto en `EducaDatos_Git`, entra en esa carpeta:

```bash
cd /Users/danielcontreras/Documents/EducaDatos_Git
git status
```

Si tienes archivos modificados, consérvalos antes de actualizar. Puedes hacer una
copia completa con Finder. No uses órdenes que borren o reemplacen tus cambios.
Con el checkout sin cambios pendientes, actualiza:

```bash
git pull --ff-only origin main
```

Si esa carpeta todavía no existe, crea una copia nueva del repositorio:

```bash
cd /Users/danielcontreras/Documents
git clone https://github.com/dacc-notbot/educaDatos_App.git EducaDatos_Git
cd EducaDatos_Git
```

Los archivos de Firebase ahora vienen con el repositorio. Conserva la carpeta
anterior hasta verificar la nueva. No copies `y/index.html` sobre la interfaz.

## 2. Publicar el servicio que responde preguntas

1. Abre [Google Cloud Console](https://console.cloud.google.com/run).
2. En el selector de proyecto superior, elige **EducaDatos / educadatos-3617c**.
3. En **Cloud Run**, elige **Crear servicio / Implementar servicio**. Los nombres
   pueden variar según el idioma de la consola.
4. Selecciona la opción de implementar continuamente desde un repositorio.
5. Conecta GitHub cuando lo pida y selecciona **dacc-notbot/educaDatos_App**.
   La autorización de Firebase Hosting no sustituye esta conexión de Cloud Build.
6. Selecciona la rama **main** y la compilación mediante **Dockerfile**.
   La ruta del archivo es `Dockerfile`, en la raíz del repositorio.
7. Usa **educadatos-api** como nombre de servicio. Elige una región y mantenla
   para las siguientes implementaciones; `us-central1` es una opción disponible.
8. Selecciona **Permitir acceso público / Permitir invocaciones sin autenticación**.
   Esto permite que cualquier visitante consulte la API sin una cuenta de Google.
9. En la configuración del contenedor, establece el puerto **8080**.
10. Como punto de partida, usa **2 CPU**, **2 GiB de memoria**, **0 instancias
    mínimas**, **2 instancias máximas** y **2 solicitudes simultáneas por instancia**.
    Ajusta estos valores después de medir el tráfico y consumo reales.
11. Si permite ajustar el tiempo máximo de solicitud, usa **300 segundos**.
12. Añade las siguientes variables de entorno del contenedor:

    | Nombre | Valor |
    | --- | --- |
    | `CORS_ORIGINS` | `https://educadatos-3617c.web.app,https://educadatos-3617c.firebaseapp.com` |
    | `MAX_CONCURRENT_ANALYSES` | `2` |
    | `OPENBLAS_NUM_THREADS` | `2` |
    | `OMP_NUM_THREADS` | `2` |

13. Confirma la implementación y espera a que termine la compilación.

Cloud Run y las compilaciones requieren facturación habilitada en el proyecto y
pueden generar cobros. Si la consola lo solicita, vincula tu cuenta de facturación;
revisa sus precios y configura un presupuesto para controlar el uso.

Cloud Run mostrará una **URL del servicio**, que empieza con `https://` y
normalmente termina en `run.app`. Copia esa dirección. Es pública y no es una clave.

Abre esa dirección añadiendo `/health` al final. Debes ver una respuesta que
contiene `"status":"ok"`. Si aparece una solicitud de acceso o un error, revisa
el acceso público y los registros del servicio antes de continuar.

En **Editar e implementar una nueva revisión**, añade también `PUBLIC_BASE_URL`
con esa URL y guarda la revisión. Esta variable anuncia la dirección pública en
el esquema de la API. No cambies el `Dockerfile` para escribir la URL.

## 3. Decirle a GitHub dónde está el servicio

1. Abre [el repositorio principal](https://github.com/dacc-notbot/educaDatos_App).
2. Entra en **Settings → Secrets and variables → Actions → Variables**.
3. Pulsa **New repository variable**.
4. En **Name**, escribe exactamente `VITE_API_BASE_URL`.
5. En **Value**, pega la URL de Cloud Run, sin `/health` ni `/chat` al final.
6. Guarda la variable.

Usa **Variables**, porque esta URL es pública. El secreto de Firebase que creó el
asistente de configuración se llama `FIREBASE_SERVICE_ACCOUNT_EDUCADATOS_3617C` y
debe conservarse en **Secrets**. No tienes que copiar su contenido a la web.

## 4. Publicar la web desde GitHub

1. En el repositorio, abre la pestaña **Actions**.
2. Selecciona **Comprobar web y publicar en Firebase**.
3. Pulsa **Run workflow**, elige **main** y confirma.
4. Abre la ejecución para seguir los pasos. Espera a que todos terminen en verde.
5. Abre [educadatos-3617c.web.app](https://educadatos-3617c.web.app/).

Añadir la variable no ejecuta el workflow por sí solo; por eso el primer
lanzamiento se inicia con **Run workflow**. Los siguientes cambios en `main`
activarán comprobación y publicación automáticamente.

Cuando la variable está vacía, el workflow solo comprueba pruebas y compilación.
Antes de publicar, Firebase comprueba `/health` en el backend y compila con su URL.
Si hay un error, revisa el paso rojo en Actions; no necesitas repetir `firebase init`.

Los canales de prueba de propuestas de cambio tienen un dominio diferente.
Si necesitas consultar desde uno, añade su origen exacto a `CORS_ORIGINS` en
Cloud Run, conservando los dos orígenes de producción.

## 5. Comprobar la página publicada

- Escribe **Hola**: debe aparecer una respuesta de EducaDatos.
- Prueba **¿Cuántos colegios oficiales y privados hay en Soacha?**.
- Comprueba que puedas abrir las fuentes de la respuesta.
- Prueba desde tu teléfono y sin iniciar sesión.
- Comprueba que las advertencias de datos sean visibles.
- Un dato no disponible debe mostrarse como **No disponible**, nunca como cero.

La primera consulta puede tardar mientras se descargan datos públicos. Una
sobrecarga devuelve un mensaje de espera; un fallo de datos.gov.co conserva tu
pregunta para volver a intentar. La disponibilidad de esa fuente sigue siendo
externa a la aplicación. Este lanzamiento necesita después supervisión y pruebas
de carga para ajustar su capacidad.

## Alternativa: publicar desde tu Mac

Desde la raíz del proyecto, comprueba `node --version`. Usa Node.js 22.12 o
posterior; se validó Node.js 24. Si necesitas instalarlo, usa el instalador para
macOS de [Node.js](https://nodejs.org/es/download).

Instala las dependencias:

```bash
npm ci --prefix web
```

Crea la configuración local:

```bash
cp web/.env.example web/.env.local
nano web/.env.local
```

Completa `VITE_API_BASE_URL=` con la URL de Cloud Run. Guarda con **Control + O**,
Enter y **Control + X**. Ese archivo queda excluido de Git.

Con Firebase CLI ya instalado e iniciado con tu cuenta, ejecuta:

```bash
firebase use educadatos-3617c
firebase deploy --only hosting --project educadatos-3617c
```

Firebase verifica el backend y compila automáticamente antes de subir los archivos.
La publicación manual y GitHub Actions actualizan el mismo sitio. La configuración
local de `.env.local` no configura GitHub; para automatizar, completa también el
paso de la variable del repositorio.
