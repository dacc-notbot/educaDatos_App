"""Consultas estructuradas compatibles con el backend reconstruido."""

from fastapi import APIRouter
from config import DATASETS, DATASET_BASE

from models.schemas import (ConsultaColegiosRequest, ConsultaProgramasRequest, ConsultaIcetexRequest,
                            TerritorioRequest, MunicipioRequest, EducaDatosResponse)
from services.adaptador_api import adaptar_servicio_para_app
from services import establecimientos_service, programas_service, bachilleres_service, icetex_service
from services import cruce_service, clustering_service

router = APIRouter(tags=["Consultas estructuradas"])


def _territorio(payload):
    return payload.municipio or payload.departamento


def _con_fuente_estadistica(resultado):
    return {**resultado, "fuentes_usadas": resultado.get("fuentes_usadas") or [DATASETS[DATASET_BASE]]}


@router.post("/colegios", response_model=EducaDatosResponse, operation_id="colegiosEstructurados")
def colegios(payload: ConsultaColegiosRequest):
    resultado = establecimientos_service.consultar_establecimientos_educativos_service(
        departamento=payload.departamento, municipio=payload.municipio, sector=payload.sector,
        limit=payload.limit, modo_respuesta=payload.modo_respuesta)
    return adaptar_servicio_para_app(resultado, f"Colegios en {_territorio(payload)}")


@router.post("/programas-superior", response_model=EducaDatosResponse, operation_id="programasEstructurados")
def programas(payload: ConsultaProgramasRequest):
    resultado = programas_service.consultar_programas_superior_service(
        departamento=payload.departamento, municipio=payload.municipio, texto=payload.texto, limit=payload.limit)
    return adaptar_servicio_para_app(resultado, f"Educación superior en {_territorio(payload) or 'Colombia'}")


@router.post("/bachilleres", response_model=EducaDatosResponse, operation_id="bachilleresEstructurados")
def bachilleres(payload: TerritorioRequest):
    resultado = bachilleres_service.consultar_bachilleres_service(
        departamento=payload.departamento, municipio=payload.municipio, limit=payload.limit)
    return adaptar_servicio_para_app(resultado, f"Bachilleres en {_territorio(payload)}")


@router.post("/icetex", response_model=EducaDatosResponse, operation_id="icetexEstructurado")
def icetex(payload: ConsultaIcetexRequest):
    resultado = icetex_service.consultar_icetex_service(
        departamento=payload.departamento, municipio=payload.municipio, tipo=payload.tipo, limit=payload.limit)
    return adaptar_servicio_para_app(resultado, f"ICETEX {payload.tipo} en {_territorio(payload)}")


@router.post("/transito-educativo", response_model=EducaDatosResponse, operation_id="transitoEstructurado")
def transito(payload: TerritorioRequest):
    resultado = cruce_service.analizar_transito_educativo_service(
        departamento=payload.departamento, municipio=payload.municipio, limit=payload.limit)
    return adaptar_servicio_para_app(resultado, f"Tránsito educativo en {_territorio(payload)}")


@router.post("/similar", response_model=EducaDatosResponse, operation_id="similaresEstructurados")
def similares(payload: MunicipioRequest):
    resultado = clustering_service.buscar_municipios_similares_service(
        departamento=payload.departamento, municipio=payload.municipio, limit=payload.limit)
    return adaptar_servicio_para_app(_con_fuente_estadistica(resultado), f"Municipios similares a {_territorio(payload)}",
                                    respuesta=f"Se consultaron municipios con indicadores similares a {_territorio(payload)}.")


@router.post("/recomendaciones", response_model=EducaDatosResponse, operation_id="recomendacionesEstructuradas")
def recomendaciones(payload: MunicipioRequest):
    resultado = clustering_service.generar_recomendaciones_municipio_service(
        departamento=payload.departamento, municipio=payload.municipio, limit=payload.limit)
    return adaptar_servicio_para_app(_con_fuente_estadistica(resultado), f"Recomendaciones para {_territorio(payload)}",
                                    respuesta=f"Se generaron recomendaciones exploratorias para {_territorio(payload)}.")
