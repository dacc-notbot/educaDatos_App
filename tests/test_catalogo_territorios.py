from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from services import catalogo_territorios_service as servicio
from services import router_territorios


def municipio(departamento, nombre, codigo):
    return {"departamento": departamento, "municipio": nombre, "c_digo_municipio": codigo}


def test_catalogo_usa_ultima_vigencia_y_descarga_todas_las_paginas(monkeypatch):
    monkeypatch.setattr(servicio, "TAMANO_PAGINA", 2)
    consulta = Mock(side_effect=[
        [{"anio": "2024"}], [{"municipios": "3", "departamentos": "2"}],
        [municipio("Antioquia", "Granada", "5313"), municipio("Meta", "Granada", "50313")],
        [municipio("Meta", "Villavicencio", "50001")],
    ])
    monkeypatch.setattr(servicio, "consultar_dataset", consulta)
    resultado = servicio.consultar_catalogo_territorios()
    assert resultado["anio"] == 2024 and "MEN" in resultado["fuente"]
    assert resultado["departamentos"] == [
        {"departamento": "Antioquia", "municipios": [{"municipio": "Granada", "codigo": "05313"}]},
        {"departamento": "Meta", "municipios": [{"municipio": "Granada", "codigo": "50313"}, {"municipio": "Villavicencio", "codigo": "50001"}]},
    ]
    assert consulta.call_args_list[1].kwargs["params_extra"]["$where"] == "a_o='2024'"
    assert [llamada.kwargs["params_extra"]["$offset"] for llamada in consulta.call_args_list[2:]] == [0, 2]
    assert not any("$q" in llamada.kwargs["params_extra"] for llamada in consulta.call_args_list)


@pytest.mark.parametrize("filas", [
    [],
    [municipio("Meta", "Villavicencio", "50001")],
    [municipio("Meta", "Villavicencio", "50001"), municipio("Meta", "Granada", "50001")],
    [municipio("Meta", "Villavicencio", "50001"), municipio("Meta", "Villavicencio", "50313")],
    [municipio("Meta", "Villavicencio", "50001"), municipio("", "Granada", "50313")],
    [municipio("Meta", "Villavicencio", "50001"), municipio("Meta", "Granada", "invalido")],
])
def test_catalogo_incompleto_o_inconsistente_no_se_publica_como_vacio(monkeypatch, filas):
    consulta = Mock(side_effect=[[{"anio": "2024"}], [{"municipios": "2", "departamentos": "1"}], filas])
    monkeypatch.setattr(servicio, "consultar_dataset", consulta)
    with pytest.raises(RuntimeError):
        servicio.consultar_catalogo_territorios()


@pytest.mark.parametrize("vigencias", [[], [{"anio": None}], [{"anio": "2024' OR 1=1"}], [{"anio": "99"}]])
def test_anio_invalido_impide_consulta_y_no_se_interpela_como_filtro(monkeypatch, vigencias):
    consulta = Mock(return_value=vigencias)
    monkeypatch.setattr(servicio, "consultar_dataset", consulta)
    with pytest.raises(RuntimeError):
        servicio.consultar_catalogo_territorios()
    assert consulta.call_count == 1


def test_catalogo_no_elimina_departamentos_si_falta_uno(monkeypatch):
    monkeypatch.setattr(servicio, "consultar_dataset", Mock(side_effect=[
        [{"anio": "2024"}], [{"municipios": "1", "departamentos": "2"}],
        [municipio("Meta", "Villavicencio", "50001")],
    ]))
    with pytest.raises(RuntimeError, match="departamentos"):
        servicio.consultar_catalogo_territorios()


def test_ruta_territorial_entrega_contrato_y_error_reintentable(monkeypatch):
    app = FastAPI()
    app.include_router(router_territorios.router)
    consultar = Mock(side_effect=[
        {"departamentos": [{"departamento": "Meta", "municipios": [{"municipio": "Villavicencio", "codigo": "50001"}]}], "fuente": "MEN", "anio": 2024},
        RuntimeError("Detalle especializado del proveedor"),
    ])
    monkeypatch.setattr(router_territorios, "consultar_catalogo_territorios", consultar)
    with TestClient(app) as cliente:
        respuesta = cliente.get("/territorios")
        assert respuesta.status_code == 200 and respuesta.json()["anio"] == 2024
        error = cliente.get("/territorios")
    assert error.status_code == 502
    assert "Vuelve a intentarlo" in error.json()["detail"]
    assert "especializado" not in error.text
