from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest

import main
from services import consulta_service
from services import directorio_colegios as fuente
from services import establecimientos_service as servicio
from services.consulta_service import (
    detectar_modo_respuesta_establecimientos,
    detectar_sector_establecimiento,
)


def colegio(codigo, nombre, sector="OFICIAL", anio="2025"):
    return {
        "a_o": anio,
        "codigo_dane": codigo,
        "nombre_establecimiento": nombre,
        "sector": sector,
        "departamento": "Meta",
        "municipio": "Villavicencio",
    }


@pytest.mark.parametrize(
    "pregunta,modo,sector",
    [
        ("colegios en villavicencio", "lista", None),
        ("Qué colegios hay en Villavicencio", "lista", None),
        ("colegios públicos en Villavicencio", "lista", "OFICIAL"),
        ("colegios privados en Villavicencio", "lista", "NO_OFICIAL"),
        ("¿Cuántos colegios oficiales y privados hay en Soacha?", "conteo", None),
        ("¿Cuántos colegios privados hay en Soacha?", "conteo", "NO_OFICIAL"),
        ("¿Cuántos colegios públicos hay en Soacha?", "conteo", "OFICIAL"),
        ("Colegios no oficiales en Soacha", "lista", "NO_OFICIAL"),
    ],
)
def test_ordenes_y_conteos(pregunta, modo, sector):
    assert detectar_modo_respuesta_establecimientos(pregunta) == modo
    assert detectar_sector_establecimiento(pregunta) == sector


def test_descarga_todas_las_paginas_de_la_vigencia_global_sin_busqueda_parcial(
    monkeypatch,
):
    descargar = Mock(
        side_effect=[
            [{"vigencia": "2025"}],
            [{"total": "3"}],
            [colegio("1", "A"), colegio("2", "B")],
            [colegio("3", "C")],
        ]
    )
    monkeypatch.setattr(fuente, "consultar_dataset", descargar)
    monkeypatch.setattr(fuente, "TAMANO_PAGINA", 2)
    datos, anio = fuente.consultar_directorio_vigente("Meta", "Villavicencio")
    assert anio == 2025 and len(datos) == 3
    assert descargar.call_args_list[0].kwargs["params_extra"] == {
        "$select": "max(a_o) as vigencia"
    }
    for llamada in descargar.call_args_list[1:]:
        where = llamada.kwargs["params_extra"]["$where"]
        assert "a_o = 2025" in where and "upper(municipio) = 'VILLAVICENCIO'" in where
        assert "q" not in llamada.kwargs
    assert descargar.call_args_list[-1].kwargs["params_extra"]["$offset"] == 2


def test_no_usa_anios_antiguos_si_el_territorio_no_tiene_registros_actuales(
    monkeypatch,
):
    descargar = Mock(side_effect=[[{"vigencia": "2025"}], [{"total": "0"}]])
    monkeypatch.setattr(fuente, "consultar_dataset", descargar)
    assert fuente.consultar_directorio_vigente("Meta", "Villavicencio") == ([], 2025)
    assert descargar.call_count == 2


@pytest.mark.parametrize("pagina", [[], [colegio("1", "A", anio="2024")]])
def test_fuente_incompleta_o_anio_incorrecto_no_produce_listado_exitoso(
    monkeypatch, pagina
):
    monkeypatch.setattr(
        fuente,
        "consultar_dataset",
        Mock(side_effect=[[{"vigencia": "2025"}], [{"total": "1"}], pagina]),
    )
    with pytest.raises(RuntimeError, match="directorio completo"):
        fuente.consultar_directorio_vigente(None, "Villavicencio")


def test_no_trunca_un_directorio_grande_para_presentarlo_como_completo(monkeypatch):
    monkeypatch.setattr(fuente, "MAX_LIMIT", 2)
    monkeypatch.setattr(
        fuente,
        "consultar_dataset",
        Mock(side_effect=[[{"vigencia": "2025"}], [{"total": "3"}]]),
    )
    with pytest.raises(RuntimeError, match="capacidad"):
        fuente.consultar_directorio_vigente(None, "Villavicencio")


def test_nombres_con_apostrofos_se_escapan_como_valores(monkeypatch):
    descargar = Mock(side_effect=[[{"vigencia": "2025"}], [{"total": "0"}]])
    monkeypatch.setattr(fuente, "consultar_dataset", descargar)
    fuente.consultar_directorio_vigente(None, "San Juan d'Arama")
    assert "'SAN JUAN D''ARAMA'" in descargar.call_args.kwargs["params_extra"]["$where"]


def test_conteos_y_filtros_usan_colegios_unicos_y_preservan_ceros(monkeypatch):
    datos = [colegio("1", "A"), colegio("1.0", "A"), colegio("2", "B", "NO_OFICIAL")]
    monkeypatch.setattr(
        servicio, "consultar_directorio_vigente", Mock(return_value=(datos, 2025))
    )
    r = servicio.consultar_establecimientos_educativos_service(
        municipio="Villavicencio", modo_respuesta="lista"
    )
    assert r["datos"]["total_establecimientos_unicos"] == 2
    assert r["datos"]["distribucion_sector"] == {"OFICIAL": 1, "NO_OFICIAL": 1}
    assert [c["tipo"] for c in r["datos"]["lista_establecimientos"]] == [
        "Público",
        "Privado",
    ]
    privado = servicio.consultar_establecimientos_educativos_service(
        municipio="Villavicencio", sector="privado"
    )
    assert "1 colegio privado" in privado["respuesta_corta"]
    assert privado["datos"]["total_establecimientos_unicos"] == 1
    assert privado["datos"]["lista_establecimientos"] == []
    monkeypatch.setattr(
        servicio,
        "consultar_directorio_vigente",
        Mock(return_value=([colegio("1", "A")], 2025)),
    )
    r = servicio.consultar_establecimientos_educativos_service(
        municipio="Villavicencio", sector="privado"
    )
    assert r["datos"]["total_establecimientos_unicos"] == 0
    assert "0 colegios privados" in r["respuesta_corta"]


def test_nombres_sin_codigo_se_deduplican_por_territorio_y_no_inventa_sector(
    monkeypatch,
):
    datos = [
        colegio("", "Colegio ÁRBOL", "DESCONOCIDO"),
        colegio("", "colegio arbol", "DESCONOCIDO"),
    ]
    monkeypatch.setattr(
        servicio, "consultar_directorio_vigente", Mock(return_value=(datos, 2025))
    )
    r = servicio.consultar_establecimientos_educativos_service(
        municipio="Villavicencio", modo_respuesta="lista"
    )
    assert r["datos"]["total_establecimientos_unicos"] == 1
    assert r["datos"]["lista_establecimientos"][0]["tipo"] == "Sin dato"
    assert any("no tienen código" in texto for texto in r["limitaciones"])


def test_sector_conflictivo_en_codigo_unico_no_se_asigna_a_publicos_o_privados(
    monkeypatch,
):
    datos = [colegio("1", "A"), colegio("1", "A", "NO_OFICIAL")]
    monkeypatch.setattr(
        servicio, "consultar_directorio_vigente", Mock(return_value=(datos, 2025))
    )
    r = servicio.consultar_establecimientos_educativos_service(
        municipio="Villavicencio", modo_respuesta="lista"
    )
    assert r["datos"]["total_establecimientos_unicos"] == 1
    assert r["datos"]["distribucion_sector"] == {"SIN DATO": 1}
    assert any("sectores diferentes" in texto for texto in r["limitaciones"])


def test_chat_y_botones_comparten_el_directorio_y_el_contrato_publico(monkeypatch):
    datos = [
        colegio("1", "Colegio A"),
        colegio("1", "Colegio A"),
        colegio("2", "Colegio B", "NO_OFICIAL"),
    ]
    monkeypatch.setattr(
        servicio, "consultar_directorio_vigente", Mock(return_value=(datos, 2025))
    )
    monkeypatch.setattr(
        consulta_service,
        "detectar_territorio",
        Mock(return_value=("Meta", "Villavicencio")),
    )
    with TestClient(main.app) as cliente:
        lista = cliente.post("/chat", json={"pregunta": "colegios en villavicencio"})
        assert lista.status_code == 200
        detalle = lista.json()["datos"]["detalle_consulta"]
        assert detalle["territorio"] == {
            "departamento": "Meta",
            "municipio": "Villavicencio",
        }
        assert detalle["consulta_completa"] is True
        assert len(detalle["lista_establecimientos"]) == 2
        assert detalle["vigencia_mas_reciente"] == 2025
        conteo = cliente.post(
            "/chat",
            json={
                "pregunta": "¿Cuántos colegios públicos y privados hay en Villavicencio?"
            },
        )
        assert conteo.status_code == 200
        assert (
            conteo.json()["datos"]["detalle_consulta"]["total_establecimientos_unicos"]
            == 2
        )
        assert (
            conteo.json()["datos"]["detalle_consulta"]["lista_establecimientos"] == []
        )
        boton = cliente.post(
            "/colegios",
            json={
                "departamento": "Meta",
                "municipio": "Villavicencio",
                "modo_respuesta": "lista",
            },
        )
        assert boton.status_code == 200
        assert (
            boton.json()["datos"]["detalle_consulta"]["lista_establecimientos"]
            == detalle["lista_establecimientos"]
        )


@pytest.mark.parametrize("vigencia", [None, "", "2025.5", "20250", "sin dato"])
def test_no_inventa_el_anio_si_la_fuente_no_lo_informa_correctamente(
    monkeypatch, vigencia
):
    monkeypatch.setattr(
        fuente, "consultar_dataset", Mock(return_value=[{"vigencia": vigencia}])
    )
    with pytest.raises(RuntimeError, match="vigencia válida"):
        fuente.consultar_directorio_vigente(None, "Villavicencio")
