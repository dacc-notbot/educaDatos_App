from fastapi import APIRouter, HTTPException

from models.schemas import (
    PreguntaRequest,
    ConsultaColegiosRequest,
    ConsultaProgramasRequest,
    ConsultaIcetexRequest,
    MunicipioRequest,
    TerritorioRequest,
)

from services.consulta_service import resolver_consulta_ciudadana
from services.establecimientos_service import consultar_establecimientos_educativos_service
from services.programas_service import consultar_programas_superior_service
from services.bachilleres_service import consultar_bachilleres_service
from services.icetex_service import consultar_icetex_service
from services.cruce_service import analizar_transito_educativo_service
from services.diagnostico_service import diagnostico_territorial_educativo_service
from services.clustering_service import (
    consultar_cluster_municipio_service,
    buscar_municipios_similares_service,
    generar_recomendaciones_municipio_service,
)


router = APIRouter(
    prefix="/ciudadano",
    tags=["Consulta ciudadana"]
)


@router.post("/chat")
def chat_ciudadano(payload: PreguntaRequest):
    try:
        return resolver_consulta_ciudadana(payload.pregunta)
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@router.post("/colegios")
def consultar_colegios(payload: ConsultaColegiosRequest):
    try:
        return consultar_establecimientos_educativos_service(
            departamento=payload.departamento,
            municipio=payload.municipio,
            sector=payload.sector,
            limit=payload.limit or 100000
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@router.post("/programas-superior")
def consultar_programas_superior(payload: ConsultaProgramasRequest):
    try:
        return consultar_programas_superior_service(
            departamento=payload.departamento,
            municipio=payload.municipio,
            texto=payload.texto,
            limit=payload.limit or 100000
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@router.post("/bachilleres")
def consultar_bachilleres(payload: TerritorioRequest):
    try:
        return consultar_bachilleres_service(
            departamento=payload.departamento,
            municipio=payload.municipio
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@router.post("/icetex")
def consultar_icetex(payload: ConsultaIcetexRequest):
    try:
        return consultar_icetex_service(
            departamento=payload.departamento,
            municipio=payload.municipio,
            tipo=payload.tipo,
            limit=payload.limit or 100000
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@router.post("/transito-educativo")
def consultar_transito_educativo(payload: TerritorioRequest):
    try:
        return analizar_transito_educativo_service(
            departamento=payload.departamento,
            municipio=payload.municipio
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@router.post("/diagnostico")
def consultar_diagnostico(payload: TerritorioRequest):
    try:
        return diagnostico_territorial_educativo_service(
            departamento=payload.departamento,
            municipio=payload.municipio
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@router.post("/grupo-estadistico")
def consultar_grupo_estadistico(payload: MunicipioRequest):
    try:
        return consultar_cluster_municipio_service(
            departamento=payload.departamento,
            municipio=payload.municipio
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@router.post("/municipios-similares")
def consultar_municipios_similares(payload: MunicipioRequest):
    try:
        return buscar_municipios_similares_service(
            departamento=payload.departamento,
            municipio=payload.municipio
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@router.post("/recomendaciones")
def consultar_recomendaciones(payload: MunicipioRequest):
    try:
        return generar_recomendaciones_municipio_service(
            departamento=payload.departamento,
            municipio=payload.municipio
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))