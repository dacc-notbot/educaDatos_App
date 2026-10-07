from typing import Any, Dict, Optional

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from models.schemas import PreguntaRequest, MunicipioRequest, TerritorioRequest, EducaDatosResponse
from services.router_ciudadano import router as router_ciudadano
from services.router_api import router as router_api
from services.adaptador_api import adaptar_consulta_para_app, adaptar_servicio_para_app
from services.establecimientos_service import consultar_establecimientos_educativos_service
from fastapi.responses import JSONResponse
import logging
import asyncio

from config import DATASETS, DATASET_BASE, PUBLIC_BASE_URL, APP_VERSION, CORS_ORIGINS, MAX_CONCURRENT_ANALYSES

from services.socrata_service import (
    consultar_dataset,
    explorar_columnas_dataset,
    buscar_en_dataset,
)

from services.consulta_service import resolver_consulta_ciudadana

from services.clustering_service import (
    obtener_metadata_clustering_service,
    consultar_clusters_municipios_service,
    consultar_cluster_municipio_service,
    buscar_municipios_similares_service,
    generar_recomendaciones_municipio_service,
)

from services.cruce_service import analizar_transito_educativo_service

from services.diagnostico_service import diagnostico_territorial_educativo_service

from services.territorio_service import (
    construir_catalogo_territorial,
    buscar_territorios_por_texto,
    detectar_territorio_nacional,
)

app = FastAPI(
    title="EducaDatos API",
    description=(
        "Backend ciudadano para consultar datos abiertos educativos de Colombia, "
        "generar diagnósticos territoriales, analizar tránsito educativo y aplicar "
        "clustering municipal."
    ),
    version=APP_VERSION,
)

cupo_analisis = asyncio.BoundedSemaphore(MAX_CONCURRENT_ANALYSES)


@app.middleware("http")
async def limitar_analisis_simultaneos(request, call_next):
    path = request.url.path
    analitica = path.startswith((
        "/chat", "/consulta", "/diagnostico", "/metadata", "/cluster", "/similar",
        "/recomendaciones", "/colegios", "/territorios", "/ciudadano", "/cruce",
        "/programas-superior", "/bachilleres", "/icetex", "/transito-educativo",
    )) or (path.startswith("/datasets/") and path.count("/") >= 3)
    if not analitica or request.method == "OPTIONS":
        return await call_next(request)
    if cupo_analisis.locked():
        return JSONResponse(
            status_code=503,
            content={"detail": "La API está ocupada. Vuelve a intentarlo en unos segundos."},
            headers={"Retry-After": "3"},
        )
    await cupo_analisis.acquire()
    try:
        return await call_next(request)
    finally:
        cupo_analisis.release()


# CORS envuelve también las respuestas de sobrecarga del middleware anterior.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)


# ============================================================
# Modelos de entrada
# ============================================================

app.include_router(router_ciudadano)
app.include_router(router_api)


@app.exception_handler(RuntimeError)
async def error_fuente_externa(request, error):
    return JSONResponse(status_code=502, content={"detail": str(error)})


@app.exception_handler(ValueError)
async def error_consulta(request, error):
    return JSONResponse(status_code=422, content={"detail": str(error)})


# ============================================================
# Utilidades de respuesta para la app Google
# ============================================================

def adaptar_respuesta_para_app(resultado: Dict[str, Any]) -> Dict[str, Any]:
    """Mantiene el contrato de /chat y recupera evidencia de los servicios."""
    return adaptar_consulta_para_app(resultado)


def adaptar_diagnostico_directo_para_app(
    resultado: Dict[str, Any], pregunta: Optional[str] = None
) -> Dict[str, Any]:
    return adaptar_servicio_para_app(resultado, pregunta)


def adaptar_cluster_directo_para_app(
    resultado: Dict[str, Any], pregunta: Optional[str] = None
) -> Dict[str, Any]:
    municipio = resultado.get("municipio_consultado")
    departamento = resultado.get("departamento")
    cluster = resultado.get("cluster_asignado", resultado.get("grupo_estadistico_asignado"))
    explicacion = resultado.get("explicacion_cluster") or resultado.get("explicacion_grupo_estadistico")
    if cluster is None:
        respuesta = f"No hay un grupo estadístico disponible para {municipio}, {departamento}."
    else:
        respuesta = f"{municipio}, {departamento}, pertenece al grupo estadístico {cluster} según los indicadores educativos disponibles."
    if explicacion:
        respuesta += f"\n\nLectura del grupo:\n- {explicacion}"
    resultado_con_fuentes = {
        **resultado,
        "fuentes_usadas": resultado.get("fuentes_usadas") or [{
            "nombre": DATASETS[DATASET_BASE]["nombre"],
            "url": DATASETS[DATASET_BASE]["url"],
        }],
    }
    return adaptar_servicio_para_app(resultado_con_fuentes, pregunta, respuesta)


# ============================================================
# Rutas básicas
# ============================================================

@app.get("/", operation_id="inicioApi")
def inicio():
    return {
        "message": "Bienvenido a EducaDatos API",
        "descripcion": (
            "API ciudadana para consultar datos abiertos educativos de Colombia, "
            "diagnóstico territorial, tránsito educativo y clustering municipal."
        ),
        "docs": "/docs",
        "health": "/health",
        "chat": "/chat",
    }


@app.get("/health", operation_id="healthCheckEducaDatos")
def health():
    return {
        "status": "ok",
        "message": "API EducaDatos funcionando correctamente",
        "proyecto": "Asistente ciudadano para datos abiertos educativos",
    }


@app.get("/verificarEstadoApi", operation_id="verificarEstadoApi")
def verificar_estado_api():
    return health()


# ============================================================
# Rutas de datasets
# ============================================================

@app.get("/datasets", operation_id="listarDatasetsEducativos")
def listar_datasets():
    return {
        "total_datasets": len(DATASETS),
        "dataset_base": DATASET_BASE,
        "datasets": DATASETS,
    }


@app.get("/datasets/{dataset_key}", operation_id="obtenerDetalleDataset")
def obtener_detalle_dataset(dataset_key: str):
    if dataset_key not in DATASETS:
        raise HTTPException(
            status_code=404,
            detail=f"No existe un dataset configurado con la clave: {dataset_key}",
        )

    return {
        "dataset_key": dataset_key,
        "detalle": DATASETS[dataset_key],
    }


@app.get("/datasets/{dataset_key}/preview", operation_id="previsualizarDatasetEducativo")
def previsualizar_dataset_educativo(
    dataset_key: str,
    limit: int = Query(
        5,
        ge=1,
        le=50,
        description="Número de registros de muestra.",
    ),
):
    try:
        registros = consultar_dataset(dataset_key=dataset_key, limit=limit)

        return {
            "dataset_key": dataset_key,
            "total_registros_devuelto": len(registros),
            "registros": registros,
        }

    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))

    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error))


@app.get("/datasets/{dataset_key}/columnas", operation_id="explorarColumnasDatasetEducativo")
def explorar_columnas_dataset_educativo(
    dataset_key: str,
    limit: int = Query(
        10,
        ge=1,
        le=50,
        description="Número de registros usados para detectar columnas.",
    ),
):
    try:
        return explorar_columnas_dataset(dataset_key=dataset_key, limit=limit)

    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))

    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error))


@app.get("/datasets/{dataset_key}/buscar", operation_id="buscarEnDatasetEducativo")
def buscar_en_dataset_educativo(
    dataset_key: str,
    texto: Optional[str] = Query(
        None,
        description="Texto libre para buscar. Ejemplo: Villavicencio, Normal Superior, ingeniería.",
    ),
    departamento: Optional[str] = Query(
        None,
        description="Departamento. Ejemplo: Meta.",
    ),
    municipio: Optional[str] = Query(
        None,
        description="Municipio. Ejemplo: Villavicencio.",
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Número máximo de registros a consultar.",
    ),
):
    try:
        return buscar_en_dataset(
            dataset_key=dataset_key,
            texto=texto,
            departamento=departamento,
            municipio=municipio,
            limit=limit,
        )

    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))

    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error))


# ============================================================
# Consulta ciudadana y chat
# ============================================================

@app.get("/consulta", response_model=EducaDatosResponse, operation_id="consultaCiudadanaEducativa")
def consulta_ciudadana_educativa(
    pregunta: str = Query(
        ...,
        min_length=3,
        description="Pregunta natural del ciudadano. Ejemplo: ¿Qué colegios hay en Villavicencio?",
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Número máximo de registros a consultar.",
    ),
):
    try:
        return resolver_consulta_ciudadana(
            pregunta=pregunta,
            limit=limit,
        )

    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))

    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error))


@app.post("/chat", response_model=EducaDatosResponse, operation_id="chatCiudadanoEducaDatos")
def chat_ciudadano(request: PreguntaRequest):
    """
    Endpoint principal para la app Google/React.

    La app envía:
    {
      "pregunta": "Haz un diagnóstico educativo de Villavicencio"
    }

    El backend responde:
    {
      "pregunta": "...",
      "respuesta": "...",
      "datos": {...},
      "fuentes": [...],
      "advertencias": [...]
    }
    """

    pregunta = request.pregunta.strip()

    if not pregunta:
        return {
            "pregunta": pregunta,
            "respuesta": "Por favor escribe una pregunta sobre educación en Colombia.",
            "datos": {},
            "fuentes": [],
            "advertencias": [],
        }

    try:
        resultado = resolver_consulta_ciudadana(
            pregunta=pregunta,
            limit=request.limit,
        )

        return adaptar_respuesta_para_app(resultado)

    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except Exception as error:
        logging.exception("Error procesando consulta ciudadana")
        raise HTTPException(status_code=500, detail="No fue posible procesar la consulta educativa.") from error


# ============================================================
# Diagnóstico territorial
# ============================================================

@app.get("/diagnostico/territorial", operation_id="generarDiagnosticoTerritorialEducativo")
def generar_diagnostico_territorial_educativo(
    departamento: Optional[str] = Query(
        None,
        description="Departamento a analizar. Ejemplo: Meta.",
    ),
    municipio: Optional[str] = Query(
        None,
        description="Municipio a analizar. Ejemplo: Villavicencio.",
    ),
    limit: int = Query(
        1000,
        ge=100,
        le=5000,
        description="Cantidad máxima de registros por consulta.",
    ),
):
    try:
        return diagnostico_territorial_educativo_service(
            departamento=departamento,
            municipio=municipio,
            limit=limit,
        )

    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))

    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error))


@app.get("/diagnostico-municipal", response_model=EducaDatosResponse, operation_id="diagnosticoMunicipalAliasGet")
def diagnostico_municipal_alias_get(
    departamento: str = Query(
        ...,
        description="Departamento. Ejemplo: Meta.",
    ),
    municipio: Optional[str] = Query(
        None,
        description="Municipio. Ejemplo: Villavicencio.",
    ),
    limit: int = Query(
        1000,
        ge=100,
        le=5000,
    ),
):
    resultado = diagnostico_territorial_educativo_service(
        departamento=departamento,
        municipio=municipio,
        limit=limit,
    )

    return adaptar_diagnostico_directo_para_app(
        resultado=resultado,
        pregunta=f"Diagnóstico educativo de {municipio or departamento}",
    )


@app.post("/diagnostico-municipal", response_model=EducaDatosResponse, operation_id="diagnosticoMunicipalAliasPost")
def diagnostico_municipal_alias_post(request: TerritorioRequest):
    resultado = diagnostico_territorial_educativo_service(
        departamento=request.departamento,
        municipio=request.municipio,
        limit=request.limit,
    )

    return adaptar_diagnostico_directo_para_app(
        resultado=resultado,
        pregunta=f"Diagnóstico educativo de {request.municipio or request.departamento}",
    )


# ============================================================
# Cruce: bachilleres, superior e ICETEX
# ============================================================

@app.get("/cruce/transito-educativo", operation_id="analizarTransitoEducativo")
def analizar_transito_educativo(
    departamento: Optional[str] = Query(
        None,
        description="Departamento a analizar. Ejemplo: Meta.",
    ),
    municipio: Optional[str] = Query(
        None,
        description="Municipio a analizar. Ejemplo: Villavicencio.",
    ),
    limit: int = Query(
        1000,
        ge=10,
        le=5000,
        description="Cantidad máxima de registros por dataset.",
    ),
):
    try:
        return analizar_transito_educativo_service(
            departamento=departamento,
            municipio=municipio,
            limit=limit,
        )

    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))

    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error))


# ============================================================
# Clustering educativo municipal
# ============================================================

@app.get("/metadata", operation_id="obtenerMetadataClustering")
def obtener_metadata_clustering(
    limit: int = Query(
        100000,
        ge=100,
        le=1000000,
    ),
):
    try:
        return obtener_metadata_clustering_service(limit=limit)

    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))

    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error))


@app.get("/cluster/municipios", operation_id="consultarClustersMunicipios")
def consultar_clusters_municipios(
    departamento: Optional[str] = Query(
        None,
        description="Departamento a filtrar. Ejemplo: Meta.",
    ),
    anio: Optional[int] = Query(
        None,
        description="Año o vigencia. Si no se envía, se usa la más reciente detectada.",
    ),
    n_clusters: Optional[int] = Query(
        None,
        ge=2,
        le=8,
        description="Número de clústeres.",
    ),
    max_resultados: int = Query(
        100,
        ge=1,
        le=500,
    ),
    limit: int = Query(
        100000,
        ge=100,
        le=1000000,
    ),
):
    try:
        return consultar_clusters_municipios_service(
            departamento=departamento,
            anio=anio,
            n_clusters=n_clusters,
            max_resultados=max_resultados,
            limit=limit,
        )

    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))

    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error))


@app.get("/cluster/municipio", operation_id="consultarClusterMunicipio")
def consultar_cluster_municipio(
    departamento: str = Query(
        ...,
        description="Departamento del municipio. Ejemplo: Meta.",
    ),
    municipio: str = Query(
        ...,
        description="Municipio a consultar. Ejemplo: Villavicencio.",
    ),
    anio: Optional[int] = Query(
        None,
        description="Año o vigencia.",
    ),
    n_clusters: Optional[int] = Query(
        None,
        ge=2,
        le=8,
    ),
    limit: int = Query(
        100000,
        ge=100,
        le=1000000,
    ),
):
    try:
        return consultar_cluster_municipio_service(
            departamento=departamento,
            municipio=municipio,
            anio=anio,
            n_clusters=n_clusters,
            limit=limit,
        )

    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))

    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error))


@app.post("/cluster-municipal", response_model=EducaDatosResponse, operation_id="clusterMunicipalAliasPost")
def cluster_municipal_alias_post(request: MunicipioRequest):
    try:
        resultado = consultar_cluster_municipio_service(
            departamento=request.departamento,
            municipio=request.municipio,
            limit=request.limit,
        )

        return adaptar_cluster_directo_para_app(
            resultado=resultado,
            pregunta=f"Clúster educativo de {request.municipio}, {request.departamento}",
        )

    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.get("/similar/municipios", operation_id="buscarMunicipiosSimilares")
def buscar_municipios_similares(
    departamento: str = Query(
        ...,
        description="Departamento del municipio base. Ejemplo: Meta.",
    ),
    municipio: str = Query(
        ...,
        description="Municipio base. Ejemplo: Villavicencio.",
    ),
    top_n: int = Query(
        5,
        ge=1,
        le=20,
    ),
    anio: Optional[int] = Query(None),
    n_clusters: Optional[int] = Query(
        None,
        ge=2,
        le=8,
    ),
    solo_mismo_departamento: bool = Query(False),
    limit: int = Query(
        100000,
        ge=100,
        le=1000000,
    ),
):
    try:
        return buscar_municipios_similares_service(
            departamento=departamento,
            municipio=municipio,
            top_n=top_n,
            anio=anio,
            n_clusters=n_clusters,
            solo_mismo_departamento=solo_mismo_departamento,
            limit=limit,
        )

    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))

    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error))


@app.get("/recomendaciones", operation_id="generarRecomendacionesMunicipio")
def generar_recomendaciones_municipio(
    departamento: str = Query(
        ...,
        description="Departamento del municipio. Ejemplo: Meta.",
    ),
    municipio: str = Query(
        ...,
        description="Municipio a consultar. Ejemplo: Villavicencio.",
    ),
    anio: Optional[int] = Query(None),
    n_clusters: Optional[int] = Query(
        None,
        ge=2,
        le=8,
    ),
    limit: int = Query(
        100000,
        ge=100,
        le=1000000,
    ),
):
    try:
        return generar_recomendaciones_municipio_service(
            departamento=departamento,
            municipio=municipio,
            anio=anio,
            n_clusters=n_clusters,
            limit=limit,
        )

    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))

    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error))


# ============================================================
# Alias útil para pruebas de colegios
# ============================================================

@app.get("/colegios", operation_id="consultarColegiosAlias")
def colegios_por_municipio(
    departamento: str = Query(..., min_length=1),
    municipio: Optional[str] = Query(None),
    sector: Optional[str] = Query(None, description="oficial, no oficial o privado"),
    limit: int = Query(1000, ge=1, le=5000),
):
    resultado = consultar_establecimientos_educativos_service(
        departamento=departamento,
        municipio=municipio,
        sector=sector,
        limit=limit,
    )
    return {
        "departamento": departamento,
        "municipio": municipio,
        "respuesta": resultado["respuesta_corta"],
        "datos": resultado["datos"],
        "fuentes": [fuente["url"] for fuente in resultado.get("fuentes_usadas", [])],
        "advertencias": resultado.get("limitaciones", []),
    }


@app.get("/territorios/catalogo", operation_id="obtenerCatalogoTerritorial")
def obtener_catalogo_territorial(
    limit: int = Query(
        100000,
        ge=100,
        le=1000000,
        description="Número máximo de registros usados para construir el catálogo territorial."
    )
):
    return construir_catalogo_territorial(limit=limit)


@app.get("/territorios/buscar", operation_id="buscarTerritorios")
def buscar_territorios(
    texto: str = Query(
        ...,
        min_length=2,
        description="Texto para buscar municipio o departamento. Ejemplo: Medellín, Pasto, Santander."
    ),
    max_resultados: int = Query(
        20,
        ge=1,
        le=100
    )
):
    return buscar_territorios_por_texto(
        texto=texto,
        max_resultados=max_resultados
    )


@app.get("/territorios/detectar", operation_id="detectarTerritorioPregunta")
def detectar_territorio_pregunta(
    pregunta: str = Query(
        ...,
        min_length=3,
        description="Pregunta ciudadana para detectar departamento y municipio."
    )
):
    departamento, municipio = detectar_territorio_nacional(pregunta)

    return {
        "pregunta": pregunta,
        "departamento_detectado": departamento,
        "municipio_detectado": municipio
    }
    
# ============================================================
# OpenAPI filtrado para GPT personalizado
# ============================================================

@app.get("/openapi-gpt.json", include_in_schema=False)
def generar_openapi_para_gpt():
    """
    Genera una versión limpia del OpenAPI para cargar en un GPT personalizado.
    Solo expone las acciones más útiles para el asistente ciudadano.
    """

    acciones_permitidas = {
    "verificarEstadoApi",
    "consultaCiudadanaEducativa",
    "chatCiudadanoEducaDatos",

    "listarDatasetsEducativos",
    "obtenerDetalleDataset",
    "previsualizarDatasetEducativo",
    "buscarEnDatasetEducativo",
    "explorarColumnasDatasetEducativo",

    "generarDiagnosticoTerritorialEducativo",
    "diagnosticoMunicipalAliasGet",
    "diagnosticoMunicipalAliasPost",

    "analizarTransitoEducativo",

    "obtenerMetadataClustering",
    "consultarClustersMunicipios",
    "consultarClusterMunicipio",
    "clusterMunicipalAliasPost",
    "buscarMunicipiosSimilares",
    "generarRecomendacionesMunicipio",

    "consultarColegiosAlias",

    "obtenerCatalogoTerritorial",
    "buscarTerritorios",
    "detectarTerritorioPregunta",
}

    esquema_original = app.openapi()

    paths_filtrados = {}

    for ruta, metodos in esquema_original.get("paths", {}).items():
        metodos_filtrados = {}

        for metodo_http, definicion in metodos.items():
            operation_id = definicion.get("operationId")

            if operation_id in acciones_permitidas:
                metodos_filtrados[metodo_http] = definicion

        if metodos_filtrados:
            paths_filtrados[ruta] = metodos_filtrados

    esquema_gpt = {
        **esquema_original,
        "info": {
            "title": "EducaDatos - Acciones para GPT Ciudadano",
            "description": (
                "API ciudadana para consultar datos abiertos educativos de Colombia, "
                "realizar diagnóstico territorial, analizar tránsito educativo y aplicar "
                "clustering municipal."
            ),
            "version": APP_VERSION,
        },
        "servers": [
            {
                "url": PUBLIC_BASE_URL.rstrip("/"),
                "description": "Servidor público de EducaDatos",
            }
        ],
        "paths": paths_filtrados,
    }

    return esquema_gpt
