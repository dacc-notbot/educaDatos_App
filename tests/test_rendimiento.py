import re
import unicodedata
import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock

import pytest

from services import bachilleres_service, establecimientos_service, icetex_service, programas_service
from services import cruce_service, diagnostico_service
from utils.normalizacion import normalizar_texto, _normalizar_corto
from fastapi.testclient import TestClient
import main
import config
from utils import cache_datos


@pytest.mark.parametrize("servicio", [establecimientos_service, icetex_service, programas_service, bachilleres_service])
def test_filtro_con_columnas_no_normaliza_toda_la_fila(servicio, monkeypatch):
    completo = Mock(side_effect=AssertionError("No se necesita recorrer toda la fila"))
    monkeypatch.setattr(servicio, "texto_completo_registro", completo)
    kwargs = {"col_departamento": "departamento", "col_municipio": "municipio"}
    if servicio is bachilleres_service:
        kwargs["col_secretaria"] = None
    registro = {"departamento": "Cundinamarca", "municipio": "Soacha", "otros": "x" * 1000}
    assert servicio.registro_coincide_territorio(registro, "Cundinamarca", "Soacha", **kwargs)
    assert not servicio.registro_coincide_territorio(registro, "Meta", "Soacha", **kwargs)
    completo.assert_not_called()


@pytest.mark.parametrize("servicio", [establecimientos_service, icetex_service, programas_service, bachilleres_service])
def test_filtro_sin_columnas_conserva_respaldo_textual(servicio):
    kwargs = {"col_departamento": None, "col_municipio": None}
    if servicio is bachilleres_service:
        kwargs["col_secretaria"] = None
    assert servicio.registro_coincide_territorio({"descripcion": "Soacha, Cundinamarca"}, "Cundinamarca", "Soacha", **kwargs)
    assert not servicio.registro_coincide_territorio({"descripcion": "Villavicencio, Meta"}, "Cundinamarca", "Soacha", **kwargs)


def test_bachilleres_conserva_coincidencia_por_secretaria():
    assert bachilleres_service.registro_coincide_territorio(
        {"departamento": "Cundinamarca", "municipio": "Otro", "secretaria": "Secretaría de Soacha"},
        "Cundinamarca", "Soacha", "departamento", "municipio", "secretaria",
    )


def test_normalizacion_acotada_equivale_al_comportamiento_original():
    def anterior(valor):
        if valor is None:
            return ""
        texto = str(valor).strip().lower()
        texto = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", texto)).strip()
    for valor in [None, " Bogotá, D.C. ", "MEDELLÍN", 2024, {"municipio": "Soacha"}, ["Meta"], "Árbol " * 1000]:
        assert normalizar_texto(valor) == anterior(valor)
    _normalizar_corto.cache_clear()
    normalizar_texto("Medellín")
    normalizar_texto("Medellín")
    assert _normalizar_corto.cache_info().hits == 1
    previo = _normalizar_corto.cache_info().currsize
    normalizar_texto("fila completa " * 1000)
    assert _normalizar_corto.cache_info().currsize == previo


def test_transito_reutiliza_programas_del_mismo_diagnostico(monkeypatch):
    consultar = Mock(side_effect=AssertionError("No repetir la consulta de programas"))
    monkeypatch.setattr(cruce_service, "consultar_programas_superior_service", consultar)
    monkeypatch.setattr(cruce_service, "consultar_bachilleres_service", Mock(return_value={"datos": {}}))
    monkeypatch.setattr(cruce_service, "consultar_icetex_service", Mock(return_value={"datos": {}}))
    programas = {"ok": True, "nombre": "programas_superior", "datos": {"datos": {"total_programas_unicos": 5}}, "error": None}
    resultado = cruce_service.analizar_transito_educativo_service(departamento="Meta", resultado_programas=programas)
    assert resultado["resumen_ejecutivo"]["programas_superior_unicos"] == 5
    consultar.assert_not_called()


def test_diagnostico_comparte_programas_y_limite_con_transito(monkeypatch):
    monkeypatch.setattr(diagnostico_service, "consultar_programas_superior_service", Mock(return_value={"datos": {}}))
    monkeypatch.setattr(diagnostico_service, "consultar_establecimientos_educativos_service", Mock(return_value={"datos": {}}))
    transito = Mock(return_value={"datos": {}})
    monkeypatch.setattr(diagnostico_service, "analizar_transito_educativo_service", transito)
    diagnostico_service.diagnostico_territorial_educativo_service(departamento="Meta")
    args = transito.call_args.kwargs
    assert args["resultado_programas"]["ok"] is True
    assert args["limit"] == diagnostico_service.consultar_programas_superior_service.call_args.kwargs["limit"]


def test_sobrecarga_rechaza_analisis_pero_permite_health_y_cors(monkeypatch):
    monkeypatch.setattr(main, "cupo_analisis", asyncio.BoundedSemaphore(0))
    origen = "https://web.example.invalid" if "*" in config.CORS_ORIGINS else config.CORS_ORIGINS[0]
    with TestClient(main.app) as client:
        r = client.post("/chat", json={"pregunta": "Hola"}, headers={"Origin": origen})
        assert r.status_code == 503 and r.headers["Retry-After"] == "3"
        assert "access-control-allow-origin" in r.headers
        assert client.get("/health").status_code == 200
        assert client.get("/datasets").status_code == 200
        assert client.options("/chat", headers={"Origin": origen, "Access-Control-Request-Method": "POST"}).status_code == 200


def test_cupo_se_recupera_despues_de_un_error(monkeypatch):
    cupo = asyncio.BoundedSemaphore(1)
    monkeypatch.setattr(main, "cupo_analisis", cupo)
    monkeypatch.setattr(main, "resolver_consulta_ciudadana", Mock(side_effect=RuntimeError("Fuente no disponible")))
    with TestClient(main.app) as client:
        assert client.post("/chat", json={"pregunta": "Colegios en Soacha"}).status_code == 502
        assert not cupo.locked()
        assert client.post("/chat", json={"pregunta": ""}).status_code == 200


def test_fuente_lenta_no_bloquea_otra_consulta(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(config, "CACHE_TTL_SECONDS", 60)
    inicio, terminar = Event(), Event()

    def descargar_lento():
        inicio.set()
        assert terminar.wait(5), "La prueba debe liberar la descarga"
        return [{"dato": "lento"}]

    with ThreadPoolExecutor(max_workers=2) as pool:
        lenta = pool.submit(cache_datos.consultar_con_cache, "https://fuente/lenta", {}, descargar_lento)
        try:
            assert inicio.wait(2)
            rapida = pool.submit(cache_datos.consultar_con_cache, "https://fuente/rapida", {}, lambda: [{"dato": "rápido"}])
            assert rapida.result(timeout=2) == [{"dato": "rápido"}]
        finally:
            terminar.set()
        assert lenta.result(timeout=2) == [{"dato": "lento"}]
    assert not cache_datos._consultas_activas


def test_descargas_identicas_se_comparten_y_liberan_claves(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(config, "CACHE_TTL_SECONDS", 60)
    inicio, terminar = Event(), Event()

    def descargar():
        inicio.set()
        assert terminar.wait(5)
        return [{"dato": 1}]

    descarga = Mock(side_effect=descargar)
    with ThreadPoolExecutor(max_workers=2) as pool:
        primera = pool.submit(cache_datos.consultar_con_cache, "https://fuente", {}, descarga)
        try:
            assert inicio.wait(2)
            segunda = pool.submit(cache_datos.consultar_con_cache, "https://fuente", {}, descarga)
        finally:
            terminar.set()
        assert primera.result(timeout=2) == segunda.result(timeout=2) == [{"dato": 1}]
    descarga.assert_called_once()
    assert not cache_datos._consultas_activas
