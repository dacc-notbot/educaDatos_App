"""La API no espera otras fuentes al fallar ni supera su plazo por acumular descargas."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic
from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest

import main
from services import consulta_service
from services import estadisticas_icetex as servicio


SERIE = [{"vigencia": "2025", "cantidad": "25", "registros": "2", "informados": "2"}]


@pytest.fixture
def executor_aislado(monkeypatch):
    executor = ThreadPoolExecutor(max_workers=4)
    futuros = []
    submit_original = executor.submit

    def submit(*args, **kwargs):
        futuro = submit_original(*args, **kwargs)
        futuros.append(futuro)
        return futuro

    monkeypatch.setattr(executor, "submit", submit)
    monkeypatch.setattr(servicio, "_executor_fuentes", executor)
    yield futuros
    executor.shutdown(wait=True, cancel_futures=True)


def test_error_de_otra_dimension_responde_sin_esperar_la_primera_bloqueada(monkeypatch, executor_aislado):
    bloqueada = Event()
    liberar = Event()

    def descargar(dataset, limit, params_extra, timeout):
        campo = params_extra["$group"]
        if campo == "vigencia":
            return SERIE
        if campo == "nivel_de_formacion":
            assert bloqueada.wait(1)
            raise RuntimeError("Falló una distribución de la fuente.")
        bloqueada.set()
        assert liberar.wait(5)
        return [{"categoria": campo, "cantidad": "25"}]

    monkeypatch.setattr(servicio, "consultar_dataset", descargar)
    with ThreadPoolExecutor(max_workers=1) as analisis:
        respuesta = analisis.submit(servicio.consultar_estadisticas_icetex)
        try:
            with pytest.raises(RuntimeError, match="Falló una distribución"):
                respuesta.result(timeout=1)
            assert not liberar.is_set()
            assert any(futuro.cancelled() for futuro in executor_aislado)
        finally:
            liberar.set()


@pytest.mark.parametrize("etapa", ["serie", "distribuciones"])
def test_plazo_total_responde_aunque_una_descarga_no_termine(monkeypatch, executor_aislado, etapa):
    bloqueada = Event()
    liberar = Event()
    monkeypatch.setattr(servicio, "PLAZO_CONSULTA_ICETEX", 0.05)

    def descargar(dataset, limit, params_extra, timeout):
        es_serie = params_extra["$group"] == "vigencia"
        if (etapa == "serie" and es_serie) or (etapa == "distribuciones" and not es_serie):
            bloqueada.set()
            assert liberar.wait(5)
        return SERIE if es_serie else [{"categoria": "A", "cantidad": "25"}]

    monkeypatch.setattr(servicio, "consultar_dataset", descargar)
    inicio = monotonic()
    try:
        with pytest.raises(RuntimeError, match="ICETEX tardó demasiado"):
            servicio.consultar_estadisticas_icetex()
        assert monotonic() - inicio < 1
        assert bloqueada.is_set() and not liberar.is_set()
        if etapa == "distribuciones":
            assert any(futuro.cancelled() for futuro in executor_aislado)
    finally:
        liberar.set()


def test_finalizacion_fuera_de_orden_conserva_orden_y_totales_completos(monkeypatch, executor_aislado):
    ultima = Event()

    def descargar(dataset, limit, params_extra, timeout):
        campo = params_extra["$group"]
        if campo == "vigencia":
            return SERIE
        if campo == "departamento_de_origen":
            assert ultima.wait(2)
        if campo == "periodo_otorgamiento":
            ultima.set()
        return [{"categoria": campo, "cantidad": "25"}]

    monkeypatch.setattr(servicio, "consultar_dataset", descargar)
    resultado = servicio.consultar_estadisticas_icetex()
    datos = resultado["datos"]
    grupos = datos["visualizacion_icetex"]["distribuciones"]
    assert [grupo["clave"] for grupo in grupos] == [dimension[0] for dimension in servicio.DIMENSIONES] + ["periodo_otorgamiento"]
    assert len(grupos) == 10
    assert all(sum(fila["cantidad"] for fila in grupo["filas"]) == 25 for grupo in grupos)
    assert datos["consulta_completa"] is True
    assert datos["total_creditos_o_beneficiarios_aproximado"] == 25


def test_presupuesto_global_descuenta_el_tiempo_de_la_serie_anual(monkeypatch, executor_aislado):
    reloj = [0.0]
    plazos_descarga = []
    monkeypatch.setattr(servicio, "monotonic", lambda: reloj[0])
    monkeypatch.setattr(servicio, "REQUEST_TIMEOUT", 60)

    def descargar(dataset, limit, params_extra, timeout):
        es_serie = params_extra["$group"] == "vigencia"
        plazos_descarga.append((es_serie, timeout))
        if es_serie:
            reloj[0] = 80.0
            return SERIE
        return [{"categoria": "A", "cantidad": "25"}]

    monkeypatch.setattr(servicio, "consultar_dataset", descargar)
    resultado = servicio.consultar_estadisticas_icetex()
    assert resultado["datos"]["consulta_completa"]
    assert plazos_descarga[0] == (True, 60)
    assert len(plazos_descarga) == 11
    assert all(timeout == 40 for es_serie, timeout in plazos_descarga if not es_serie)


def test_comparacion_comparte_plazo_y_descuenta_el_primer_reporte(monkeypatch, executor_aislado):
    reloj = [0.0]
    plazos_descarga = []
    monkeypatch.setattr(servicio, "monotonic", lambda: reloj[0])
    monkeypatch.setattr(servicio, "REQUEST_TIMEOUT", 60)
    monkeypatch.setattr(consulta_service, "detectar_territorio", Mock(return_value=("Meta", None)))

    def descargar(dataset, limit, params_extra, timeout):
        es_serie = params_extra["$group"] == "vigencia"
        plazos_descarga.append((dataset, es_serie, timeout))
        if es_serie:
            if dataset == "icetex_otorgados":
                reloj[0] = 80.0
            return SERIE
        return [{"categoria": "A", "cantidad": "25"}]

    monkeypatch.setattr(servicio, "consultar_dataset", descargar)
    resultado = consulta_service.resolver_consulta_ciudadana("ICETEX otorgados y renovados en Meta")
    partes = resultado["resultados"]["datos"]["comparacion_icetex"]
    assert [parte["tipo_credito"] for parte in partes] == ["otorgados", "renovados"]
    assert len(plazos_descarga) == 22
    assert plazos_descarga[0] == ("icetex_otorgados", True, 60)
    assert all(timeout == 40 for dataset, _, timeout in plazos_descarga if dataset == "icetex_renovados")
    assert all(parte["consulta_completa"] and len(parte["visualizacion_icetex"]["distribuciones"]) == 10 for parte in partes)
    assert all(parte["visualizacion_icetex"]["total"] == 25 for parte in partes)
    assert resultado["total_resultados"] is None


def test_chat_no_publica_comparacion_parcial_si_segundo_reporte_agota_plazo(monkeypatch, executor_aislado):
    liberar = Event()
    segunda_bloqueada = Event()
    descargas = []
    monkeypatch.setattr(servicio, "PLAZO_CONSULTA_ICETEX", 0.08)
    monkeypatch.setattr(consulta_service, "detectar_territorio", Mock(return_value=("Meta", None)))

    def descargar(dataset, limit, params_extra, timeout):
        descargas.append(dataset)
        if dataset == "icetex_renovados":
            segunda_bloqueada.set()
            assert liberar.wait(5)
        return SERIE if params_extra["$group"] == "vigencia" else [{"categoria": "A", "cantidad": "25"}]

    monkeypatch.setattr(servicio, "consultar_dataset", descargar)
    try:
        with TestClient(main.app) as cliente:
            respuesta = cliente.post("/chat", json={"pregunta": "ICETEX otorgados y renovados en Meta"})
        assert respuesta.status_code == 502
        assert "ICETEX tardó demasiado" in respuesta.json()["detail"]
        assert "datos" not in respuesta.json()
        assert segunda_bloqueada.is_set() and not liberar.is_set()
        assert descargas.count("icetex_otorgados") == 11
        assert descargas.count("icetex_renovados") == 1
    finally:
        liberar.set()


def test_chat_icetex_simple_descuenta_el_tiempo_de_detectar_territorio(monkeypatch, executor_aislado):
    reloj = [0.0]
    plazos_descarga = []
    monkeypatch.setattr(servicio, "monotonic", lambda: reloj[0])
    monkeypatch.setattr(servicio, "REQUEST_TIMEOUT", 60)

    def detectar(pregunta):
        reloj[0] = 80.0
        return "Meta", None

    def descargar(dataset, limit, params_extra, timeout):
        plazos_descarga.append(timeout)
        return SERIE if params_extra["$group"] == "vigencia" else [{"categoria": "A", "cantidad": "25"}]

    monkeypatch.setattr(consulta_service, "detectar_territorio", detectar)
    monkeypatch.setattr(servicio, "consultar_dataset", descargar)
    resultado = consulta_service.resolver_consulta_ciudadana("ICETEX en Meta")
    datos = resultado["resultados"]["datos"]
    assert plazos_descarga == [40] * 11
    assert datos["consulta_completa"]
    assert len(datos["visualizacion_icetex"]["distribuciones"]) == 10
    assert datos["visualizacion_icetex"]["total"] == 25
