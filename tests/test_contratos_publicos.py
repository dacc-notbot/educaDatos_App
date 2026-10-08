"""Regresiones de las rutas públicas y del filtro de estado heredado."""

from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest

import main
from config import DEFAULT_ANALYTIC_LIMIT
from services import programas_service
from services import router_ciudadano


def test_consulta_get_expone_el_mismo_contrato_ciudadano_que_chat(monkeypatch):
    interno = {
        "pregunta_recibida": "Arquitectura en Meta",
        "intencion_detectada": "consultar_programas_superior",
        "dataset_usado": "programas_superior",
        "territorio_detectado": {"departamento": "Meta", "municipio": None},
        "respuesta_ciudadana": {
            "respuesta_corta": "Hay cuatro ofertas de Arquitectura en Meta.",
            "hallazgos_principales": [],
            "sugerencias_de_siguiente_pregunta": ["Arquitectura en Villavicencio"],
            "fuente_usada": {"nombre": "MEN", "url": "https://www.datos.gov.co/resource/upr9-nkiz.json"},
        },
        "resultados": {
            "datos": {"total_ofertas": 4, "lista_oferta": []},
            "limitaciones": ["La fuente no informa el año de registro."],
        },
    }
    monkeypatch.setattr(main, "resolver_consulta_ciudadana", Mock(return_value=interno))
    with TestClient(main.app) as cliente:
        consulta = cliente.get("/consulta", params={"pregunta": "Arquitectura en Meta"})
        chat = cliente.post("/chat", json={"pregunta": "Arquitectura en Meta"})
    assert consulta.status_code == chat.status_code == 200
    assert consulta.json() == chat.json()
    publico = consulta.json()
    assert publico["respuesta"] == "Hay cuatro ofertas de Arquitectura en Meta."
    assert publico["pregunta"] == "Arquitectura en Meta"
    assert publico["datos"]["detalle_consulta"]["total_ofertas"] == 4
    assert "MEN" in publico["fuentes"]
    assert publico["advertencias"] == ["La fuente no informa el año de registro."]


@pytest.mark.parametrize("estado", ["Activo", "Inactivo", None])
def test_programas_ciudadano_aplica_estado_a_la_oferta_y_sus_totales(monkeypatch, estado):
    registros = [
        {
            "nombreprograma": "Meta",
            "nombredepartprograma": "Meta",
            "codigoprograma": "50",
            "nombremunicipioprograma": "Villavicencio",
            "nombreinstitucion": "Universidad de ejemplo",
            "nombretituloobtenido": "ARQUITECTO",
            "nombreestadoprograma": estado_publicado,
            "nombrenivelformacion": "Universitaria",
            "nombremetodologia": "Presencial",
        }
        for estado_publicado in ["Activo", "Inactivo"]
    ]
    monkeypatch.setattr(programas_service, "consultar_dataset", Mock(return_value=registros))
    monkeypatch.setattr(programas_service, "construir_procedencia_oferta", Mock(return_value={}))
    payload = {"municipio": "Villavicencio", "texto": "Arquitectura"}
    if estado is not None:
        payload["estado"] = estado
    with TestClient(main.app) as cliente:
        respuesta = cliente.post("/ciudadano/programas-superior", json=payload)
    assert respuesta.status_code == 200
    datos = respuesta.json()["datos"]
    esperados = {estado} if estado is not None else {"Activo", "Inactivo"}
    assert {fila["estado"] for fila in datos["lista_oferta"]} == esperados
    assert {fila["estado"] for fila in datos["resumen_oferta"]["por_estado"]} == esperados
    assert datos["resumen_oferta"]["total_ofertas"] == len(esperados)


def test_estado_invalido_se_rechaza_sin_consultar_la_fuente(monkeypatch):
    descargar = Mock(side_effect=AssertionError("No debe descargar una solicitud inválida."))
    monkeypatch.setattr(programas_service, "consultar_dataset", descargar)
    with TestClient(main.app) as cliente:
        respuesta = cliente.post("/ciudadano/programas-superior", json={"estado": "Pendiente"})
    assert respuesta.status_code == 422
    descargar.assert_not_called()


@pytest.mark.parametrize(
    "payload,esperados",
    [
        ({}, {"departamento": None, "municipio": None, "tipo": "otorgados", "limit": DEFAULT_ANALYTIC_LIMIT, "anio": None, "filtros": {}}),
        (
            {"departamento": "Meta", "tipo": "renovados", "anio": 2022, "filtros": {"nivel_de_formacion": "PREGRADO", "estrato_socio_economico": "2"}},
            {"departamento": "Meta", "municipio": None, "tipo": "renovados", "limit": DEFAULT_ANALYTIC_LIMIT, "anio": 2022, "filtros": {"nivel_de_formacion": "PREGRADO", "estrato_socio_economico": "2"}},
        ),
    ],
)
def test_icetex_ciudadano_conserva_anio_y_filtros_explicitos_y_defaults(monkeypatch, payload, esperados):
    servicio = Mock(return_value={"respuesta_corta": "Resumen ICETEX", "datos": {"consulta_completa": True}})
    monkeypatch.setattr(router_ciudadano, "consultar_icetex_service", servicio)
    with TestClient(main.app) as cliente:
        respuesta = cliente.post("/ciudadano/icetex", json=payload)
    assert respuesta.status_code == 200
    servicio.assert_called_once_with(**esperados)
    assert respuesta.json()["datos"]["consulta_completa"] is True


@pytest.mark.parametrize(
    "filtros",
    [{"universidad": "Universidad A"}, {"estrato_socio_economico": "9"}, {"nivel_de_formacion": "   "}],
)
def test_icetex_ciudadano_rechaza_filtro_invalido_antes_del_servicio(monkeypatch, filtros):
    servicio = Mock(side_effect=AssertionError("No debe consultar ICETEX con filtros inválidos."))
    monkeypatch.setattr(router_ciudadano, "consultar_icetex_service", servicio)
    with TestClient(main.app) as cliente:
        respuesta = cliente.post("/ciudadano/icetex", json={"anio": 2022, "filtros": filtros})
    assert respuesta.status_code == 422
    servicio.assert_not_called()
