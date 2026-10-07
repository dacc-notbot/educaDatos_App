"""Regresiones de la adaptación del ZIP al backend principal."""

import asyncio
from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest

import config
import main
from services import router_api
from services.adaptador_api import adaptar_consulta_para_app, adaptar_servicio_para_app


@pytest.fixture
def client():
    with TestClient(main.app) as cliente:
        yield cliente


def test_chat_conserva_fuentes_anidadas_y_todas_las_advertencias(client, monkeypatch):
    fuente = {"nombre": "MEN", "url": "https://www.datos.gov.co/resource/upr9-nkiz.json"}
    resultado = {
        "pregunta_recibida": "Programas en Meta", "total_resultados": None,
        "respuesta_ciudadana": {"respuesta_corta": "Solo hay títulos identificables.",
                                "fuente_usada": fuente, "limitaciones": "Verificar vigencia."},
        "resultados": {"datos": {"total_programas_unicos": None}, "fuentes_usadas": [fuente],
                       "limitaciones": ["No se pueden contar programas únicos.", "Verificar vigencia."],
                       "advertencias": ["La identificación está inconsistente."]},
    }
    resolver = Mock(return_value=resultado)
    monkeypatch.setattr(main, "resolver_consulta_ciudadana", resolver)
    r = client.post("/chat", json={"pregunta": "Programas en Meta", "limit": 1234})
    assert r.status_code == 200
    data = r.json()
    assert data["fuentes"] == [fuente["nombre"], fuente["url"]]
    assert set(data["advertencias"]) == {"Verificar vigencia.", "No se pueden contar programas únicos.", "La identificación está inconsistente."}
    assert data["datos"]["detalle_consulta"]["total_programas_unicos"] is None
    assert data["datos"]["total_resultados"] is None
    assert data["respuesta_ciudadana"]["respuesta_corta"] == "Solo hay títulos identificables."
    assert data["respuesta_ciudadana"]["limitaciones"] == data["advertencias"]
    assert resolver.call_args.kwargs["limit"] == 1234


def test_diagnostico_informa_fallo_parcial_sin_leer_filas_como_advertencias():
    resultado = {"respuesta_ciudadana": {"respuesta_corta": "Diagnóstico parcial."},
                 "componentes": {"programas": {"ok": False, "error": "Fuente no disponible"}},
                 "datos": {"filas": [{"advertencias": ["Texto de una fila, no de la API"]}]}}
    data = adaptar_servicio_para_app(resultado, "Diagnóstico")
    assert data["advertencias"] == ["Componente no disponible: Fuente no disponible"]
    assert data["respuesta"] == "Diagnóstico parcial."


def test_adaptador_recupera_advertencias_del_cruce_sin_ciclos():
    servicio = {"respuesta_corta": "Cruce educativo.", "limitaciones": ["Vigencias diferentes."],
                "componentes_crudos": {"programas": {"ok": True, "datos": {"limitaciones": ["Identificación inconsistente."]}}}}
    servicio["resultados"] = servicio
    resultado = adaptar_consulta_para_app(servicio)
    assert resultado["advertencias"] == ["Vigencias diferentes.", "Identificación inconsistente."]


@pytest.mark.parametrize("ruta, modulo, funcion, payload", [
    ("/colegios", "establecimientos_service", "consultar_establecimientos_educativos_service", {"municipio": "Soacha", "sector": "privado", "modo_respuesta": "lista"}),
    ("/programas-superior", "programas_service", "consultar_programas_superior_service", {"municipio": "Soacha", "texto": "Ingeniería"}),
    ("/bachilleres", "bachilleres_service", "consultar_bachilleres_service", {"departamento": "Meta"}),
    ("/icetex", "icetex_service", "consultar_icetex_service", {"departamento": "Meta", "tipo": "renovados"}),
    ("/transito-educativo", "cruce_service", "analizar_transito_educativo_service", {"departamento": "Meta"}),
    ("/similar", "clustering_service", "buscar_municipios_similares_service", {"departamento": "Meta", "municipio": "Villavicencio"}),
    ("/recomendaciones", "clustering_service", "generar_recomendaciones_municipio_service", {"departamento": "Meta", "municipio": "Villavicencio"}),
])
def test_rutas_zip_ejecutan_servicio_y_entregan_contrato_comun(client, monkeypatch, ruta, modulo, funcion, payload):
    servicio = Mock(return_value={"respuesta_corta": "Consulta verificada.", "datos": {"total": 0},
                                 "fuentes_usadas": [{"url": "https://www.datos.gov.co"}],
                                 "limitaciones": ["Lectura exploratoria."]})
    monkeypatch.setattr(getattr(router_api, modulo), funcion, servicio)
    r = client.post(ruta, json={**payload, "limit": 1234})
    assert r.status_code == 200, r.text
    data = r.json()
    assert {"pregunta", "respuesta", "datos", "fuentes", "advertencias", "respuesta_ciudadana"} <= data.keys()
    assert data["datos"]["detalle_consulta"]["total"] == 0
    assert data["fuentes"] == ["https://www.datos.gov.co"]
    assert data["advertencias"] == ["Lectura exploratoria."]
    assert servicio.call_args.kwargs["limit"] == 1234
    for clave, valor in payload.items():
        assert servicio.call_args.kwargs[clave] == valor


@pytest.mark.parametrize("payload", [{}, {"departamento": " "}, {"municipio": " "},
                                      {"departamento": "Meta", "limit": 0},
                                      {"departamento": "Meta", "limit": config.MAX_LIMIT + 1},
                                      {"departamento": "Meta", "limit": None},
                                      {"departamento": "Meta", "sector": "inventado"}])
def test_entradas_invalidas_no_consultan_la_fuente(client, monkeypatch, payload):
    servicio = Mock(side_effect=AssertionError("No descargar con entrada inválida"))
    monkeypatch.setattr(router_api.establecimientos_service, "consultar_establecimientos_educativos_service", servicio)
    assert client.post("/colegios", json=payload).status_code == 422
    servicio.assert_not_called()


def test_icetex_rechaza_tipo_desconocido(client):
    assert client.post("/icetex", json={"departamento": "Meta", "tipo": "inventado"}).status_code == 422


def test_diagnostico_departamental_post_y_limite_funcionan(client, monkeypatch):
    servicio = Mock(return_value={"respuesta_ciudadana": {"respuesta_corta": "Diagnóstico de Meta."},
                                 "componentes": {}})
    monkeypatch.setattr(main, "diagnostico_territorial_educativo_service", servicio)
    r = client.post("/diagnostico-municipal", json={"departamento": "Meta", "limit": 5000})
    assert r.status_code == 200 and r.json()["respuesta"] == "Diagnóstico de Meta."
    assert servicio.call_args.kwargs == {"departamento": "Meta", "municipio": None, "limit": 5000}


@pytest.mark.parametrize("error, status", [(ValueError("Municipio no encontrado"), 404), (RuntimeError("Fuente no disponible"), 502)])
def test_cluster_no_disfraza_errores_como_http_200(client, monkeypatch, error, status):
    monkeypatch.setattr(main, "consultar_cluster_municipio_service", Mock(side_effect=error))
    r = client.post("/cluster-municipal", json={"departamento": "Meta", "municipio": "Villavicencio"})
    assert r.status_code == status and r.json()["detail"] == str(error)


def test_grupo_cero_y_explicacion_no_se_pierden(client, monkeypatch):
    monkeypatch.setattr(main, "consultar_cluster_municipio_service", Mock(return_value={
        "departamento": "Meta", "municipio_consultado": "Villavicencio", "cluster_asignado": 0,
        "explicacion_cluster": "Indicadores semejantes.", "advertencias_o_limitaciones": ["No es un ranking."]}))
    r = client.post("/cluster-municipal", json={"departamento": "Meta", "municipio": "Villavicencio"})
    assert r.status_code == 200
    assert "grupo estadístico 0" in r.json()["respuesta"]
    assert r.json()["advertencias"] == ["No es un ranking."]


@pytest.mark.parametrize("ruta", ["/programas-superior", "/bachilleres", "/icetex", "/transito-educativo"])
def test_limite_de_carga_tambien_protege_las_nuevas_rutas(client, monkeypatch, ruta):
    monkeypatch.setattr(main, "cupo_analisis", asyncio.BoundedSemaphore(0))
    r = client.post(ruta, json={"departamento": "Meta"})
    assert r.status_code == 503 and r.headers["Retry-After"] == "3"
    assert client.get("/health").status_code == 200


def test_prefijo_ciudadano_conserva_salida_y_honra_limite(client, monkeypatch):
    from services import router_ciudadano
    servicio = Mock(return_value={"respuesta_corta": "Bachilleres.", "datos": {"total": 20}})
    monkeypatch.setattr(router_ciudadano, "consultar_bachilleres_service", servicio)
    r = client.post("/ciudadano/bachilleres", json={"municipio": "Soacha", "limit": 1234})
    assert r.status_code == 200 and r.json()["datos"]["total"] == 20
    assert servicio.call_args.kwargs == {"departamento": None, "municipio": "Soacha", "limit": 1234}


@pytest.mark.parametrize("ruta, funcion", [("/similar", "buscar_municipios_similares_service"),
                                          ("/recomendaciones", "generar_recomendaciones_municipio_service")])
def test_analitica_identifica_la_fuente_configurada(client, monkeypatch, ruta, funcion):
    monkeypatch.setattr(router_api.clustering_service, funcion, Mock(return_value={"resultados": []}))
    r = client.post(ruta, json={"departamento": "Meta", "municipio": "Villavicencio"})
    assert r.status_code == 200
    assert config.DATASETS[config.DATASET_BASE]["url"] in r.json()["fuentes"]


def test_openapi_documenta_el_contrato_y_todas_las_rutas_zip(client):
    esquema = client.get("/openapi.json").json()
    rutas_zip = ["/chat", "/diagnostico-municipal", "/cluster-municipal", "/colegios",
                 "/similar", "/recomendaciones", "/transito-educativo"]
    for ruta in rutas_zip:
        response = esquema["paths"][ruta]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
        assert response["$ref"].endswith("/EducaDatosResponse")
