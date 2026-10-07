from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest

import config
import main
import probar_backend
from services import bachilleres_service, establecimientos_service, icetex_service
from services import territorio_service
from utils import cache_datos
from utils.normalizacion import valor_a_numero


@pytest.mark.parametrize("entrada, esperado", [
    ("56.11", 56.11), (56.11, 56.11), ("2024.0", 2024),
    ("56,11%", 56.11), ("1.234,56", 1234.56), ("1,234.56", 1234.56),
    ("$ 1.234.567,89", 1234567.89), ("1.234.567", 1234567), ("1,234,567", 1234567),
    ("0", 0), ("-3.5", -3.5), (None, None), ("sin dato", None),
    (float("nan"), None), ("Infinity", None),
])
def test_numeros_socrata_y_formato_local(entrada, esperado):
    for convertir in [valor_a_numero, bachilleres_service.valor_a_numero,
                      establecimientos_service.valor_a_numero, icetex_service.valor_a_numero]:
        assert convertir(entrada) == esperado


@pytest.fixture
def cliente():
    with TestClient(main.app) as client:
        yield client


def test_api_publica_y_esquema_unificado(cliente):
    assert cliente.get("/health").json()["status"] == "ok"
    esquema = cliente.get("/openapi.json").json()
    assert esquema["info"]["version"] == config.APP_VERSION
    assert "/ciudadano/colegios" in esquema["paths"]
    assert esquema["components"]["schemas"]["PreguntaRequest"]["properties"]["pregunta"]["maxLength"] == 2000
    assert cliente.get("/openapi-gpt.json").json()["servers"][0]["url"] == config.PUBLIC_BASE_URL
    assert cliente.post("/chat", json={"pregunta": " "}).status_code == 200
    assert cliente.post("/chat", json={"pregunta": "x" * 2001}).status_code == 422
    assert cliente.post("/cluster-municipal", json={"departamento": " ", "municipio": "Soacha"}).status_code == 422


def test_error_de_fuente_no_se_presenta_como_exito(cliente, monkeypatch):
    monkeypatch.setattr(main, "resolver_consulta_ciudadana", Mock(side_effect=RuntimeError("Fuente no disponible")))
    respuesta = cliente.post("/chat", json={"pregunta": "Colegios en Soacha"})
    assert respuesta.status_code == 502
    monkeypatch.setattr(main, "diagnostico_territorial_educativo_service", Mock(side_effect=RuntimeError("Fuente no disponible")))
    assert cliente.get("/diagnostico-municipal", params={"departamento": "Meta"}).status_code == 502


def test_sector_de_colegios_se_envia_al_servicio(cliente, monkeypatch):
    servicio = Mock(return_value={"respuesta_corta": "2 colegios", "datos": {"total_establecimientos_unicos": 2}, "fuentes_usadas": []})
    monkeypatch.setattr(main, "consultar_establecimientos_educativos_service", servicio)
    respuesta = cliente.get("/colegios", params={"departamento": "Meta", "municipio": "Villavicencio", "sector": "privado"})
    assert respuesta.status_code == 200
    assert respuesta.json()["datos"]["total_establecimientos_unicos"] == 2
    assert servicio.call_args.kwargs["sector"] == "privado"


@pytest.fixture
def cache_local(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(config, "CACHE_TTL_SECONDS", 60)
    monkeypatch.setattr(config, "CACHE_MAX_ENTRIES", 2)
    return tmp_path


def test_cache_reutiliza_solo_consultas_iguales_y_expira(cache_local, monkeypatch):
    descargar = Mock(return_value=[{"municipio": "Soacha"}])
    monkeypatch.setattr(cache_datos.time, "time", lambda: 100)
    assert cache_datos.consultar_con_cache("https://fuente", {"limit": 1}, descargar) == [{"municipio": "Soacha"}]
    cache_datos.consultar_con_cache("https://fuente", {"limit": 1}, descargar)
    assert descargar.call_count == 1
    cache_datos.consultar_con_cache("https://fuente", {"limit": 2}, descargar)
    assert descargar.call_count == 2
    monkeypatch.setattr(cache_datos.time, "time", lambda: 161)
    cache_datos.consultar_con_cache("https://fuente", {"limit": 1}, descargar)
    assert descargar.call_count == 3


def test_cache_no_guarda_errores_y_limita_archivos(cache_local):
    fallar = Mock(side_effect=RuntimeError("Fuente no disponible"))
    with pytest.raises(RuntimeError):
        cache_datos.consultar_con_cache("https://fuente", {}, fallar)
    assert not list(cache_local.iterdir())
    for limite in range(3):
        cache_datos.consultar_con_cache("https://fuente", {"limit": limite}, lambda: [{"dato": 1}])
    assert len(list(cache_local.glob("*.json"))) == 2


def test_cache_desactivada(cache_local, monkeypatch):
    monkeypatch.setattr(config, "CACHE_TTL_SECONDS", 0)
    descargar = Mock(return_value=[])
    for _ in range(2):
        cache_datos.consultar_con_cache("https://fuente", {}, descargar)
    assert descargar.call_count == 2
    assert not list(cache_local.iterdir())


def test_catalogo_parcial_no_contamina_deteccion_completa(monkeypatch):
    monkeypatch.setattr(territorio_service, "CACHE_TERRITORIOS", {"catalogo": None, "limit": None, "vence": 0})
    descargar = Mock(side_effect=[
        [{"departamento": "Antioquia", "municipio": "Abriaquí"}],
        [{"departamento": "Cundinamarca", "municipio": "Soacha"}],
    ])
    monkeypatch.setattr(territorio_service, "consultar_dataset", descargar)
    territorio_service.construir_catalogo_territorial(limit=100)
    assert territorio_service.detectar_territorio_nacional("Colegios en Soacha") == ("Cundinamarca", "Soacha")
    assert descargar.call_count == 2


def test_runner_rechaza_fallback_con_http_200():
    sesion = Mock()
    sesion.post.return_value.status_code = 200
    sesion.post.return_value.json.return_value = {"respuesta": "No pude consultar datos.gov.co en este momento."}
    resultado = probar_backend.probar_chat(sesion, "Colegios en Soacha")
    assert not resultado["ok"]
    assert resultado["advertencias"]


def test_clustering_usa_la_vigencia_socrata_y_conserva_decimales():
    import pandas as pd
    from services.clustering_service import detectar_columnas_base, filtrar_por_departamento_y_anio, valor_a_float
    datos = pd.DataFrame([
        {"a_o": "2023", "departamento": "Meta", "municipio": "Villavicencio", "cobertura": "56.11"},
        {"a_o": "2024", "departamento": "Meta", "municipio": "Villavicencio", "cobertura": "57.12"},
    ])
    columnas = detectar_columnas_base(datos)
    assert columnas["anio"] == "a_o"
    filtrado, _, anio = filtrar_por_departamento_y_anio(datos, columnas)
    assert anio == 2024 and len(filtrado) == 1
    assert valor_a_float(filtrado.iloc[0]["cobertura"]) == 57.12


def test_programas_usan_sede_del_programa_y_codigo_unico(monkeypatch):
    from services import programas_service
    registros = [
        {"nombredepartprograma": "Cundinamarca", "nombremunicipioprograma": "Soacha",
         "nombredepartinstitucion": "Bogotá", "nombremunicipioinstitucion": "Bogotá",
         "codigoprograma": codigo, "nombreprograma": "Ingeniería", "nombreinstitucion": "Universidad",
         "nombreestadoprograma": "Activo"}
        for codigo in ["100", "200"]
    ]
    monkeypatch.setattr(programas_service, "consultar_dataset", Mock(return_value=registros))
    resultado = programas_service.consultar_programas_superior_service(departamento="Cundinamarca", municipio="Soacha")
    datos = resultado["datos"]
    assert datos["total_programas_unicos"] == 2
    assert datos["total_programas_activos_unicos"] == 2
    assert datos["columnas_detectadas"]["municipio"] == "nombremunicipioprograma"


def test_seleccion_columnas_respeta_prioridad_y_no_excluye_cantidad():
    from services.socrata_service import seleccionar_columna_por_patrones
    registros = [{"municipio_institucion": "Bogotá", "municipio_programa": "Soacha", "cantidad": 5}]
    assert seleccionar_columna_por_patrones(registros, ["municipio_programa", "municipio_institucion"]) == "municipio_programa"
    assert seleccionar_columna_por_patrones(registros, ["cantidad"], excluir=["id"]) == "cantidad"


def test_fuente_programas_inconsistente_no_inventa_conteos(monkeypatch):
    from services import programas_service
    registros = [{"nombredepartprograma": "Antioquia", "nombremunicipioprograma": "Medellín",
                  "codigoprograma": "5", "nombreprograma": "Antioquia", "nombreinstitucion": "Universidad",
                  "nombretituloobtenido": "PSICÓLOGO", "nombreestadoprograma": "Activo"}]
    monkeypatch.setattr(programas_service, "consultar_dataset", Mock(return_value=registros))
    resultado = programas_service.consultar_programas_superior_service(municipio="Medellín")
    assert resultado["datos"]["total_programas_unicos"] is None
    assert resultado["datos"]["total_titulos_distintos"] == 1
    assert resultado["datos"]["muestra_programas"][0]["titulo_obtenido"] == "PSICÓLOGO"
    assert "inconsistencia" in resultado["respuesta_corta"]
    assert any("inconsistencia" in mensaje for mensaje in resultado["limitaciones"])
