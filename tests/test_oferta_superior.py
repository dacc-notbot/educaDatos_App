from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest

import main
from services import consulta_service, programas_service
from services.busqueda_programas import extraer_nombre_programa
from services.adaptador_api import adaptar_servicio_para_app


def registro(
    titulo="INGENIERO DE SISTEMAS",
    estado="Activo",
    municipio="Villavicencio",
    institucion="Universidad A",
):
    return {
        "nombreprograma": "Meta",
        "nombredepartprograma": "Meta",
        "codigoprograma": "50",
        "nombremunicipioprograma": municipio,
        "nombreinstitucion": institucion,
        "nombretituloobtenido": titulo,
        "nombreestadoprograma": estado,
        "nombrenivelformacion": "Universitaria",
    }


@pytest.mark.parametrize(
    "pregunta,nombre",
    [
        ("¿Qué títulos de educación superior se reportan en Meta?", None),
        ("Ingeniería de Sistemas en Meta", "ingenieria de sistemas"),
        ("Arquitectura", "arquitectura"),
        ('Programa "Diseño Gráfico" en Meta', "Diseño Gráfico"),
        ("¿Qué universidades ofrecen Psicología en Meta?", "psicologia"),
    ],
)
def test_extraccion_precisa_y_buscador_nacional(pregunta, nombre):
    assert extraer_nombre_programa(pregunta, departamento="Meta") == nombre


def test_oferta_muestra_estado_nivel_e_institucion_sin_ocultar_inactivos(monkeypatch):
    filas = [
        registro(),
        registro(estado="Inactivo"),
        registro(),
        registro(institucion="Universidad B"),
    ]
    descargar = Mock(return_value=filas)
    monkeypatch.setattr(programas_service, "consultar_dataset", descargar)
    monkeypatch.setattr(
        programas_service, "obtener_municipios_departamento", Mock(return_value=set())
    )
    r = programas_service.consultar_programas_superior_service(
        texto="Ingeniería de Sistemas"
    )
    assert len(r["datos"]["lista_oferta"]) == 3
    assert {f["estado"] for f in r["datos"]["lista_oferta"]} == {"Activo", "Inactivo"}
    assert all(
        f["nivel"] == "Universitaria" and f["institucion"]
        for f in r["datos"]["lista_oferta"]
    )
    assert r["datos"]["total_programas_unicos"] is None
    assert "inconsistencia" not in r["respuesta_corta"]
    assert "registros descargados" not in r["respuesta_corta"].lower()
    assert r["hallazgos_principales"] == []
    assert descargar.call_args.kwargs["q"] is None
    assert any("inconsistencia" in texto for texto in r["limitaciones"])
    colecciones = adaptar_servicio_para_app(r)["datos"]["colecciones"]
    assert colecciones[0]["titulo"] == "Oferta de educación superior"
    assert not colecciones[0]["es_muestra"]


def test_no_confunde_area_amplia_con_nombre_de_programa_y_respeta_territorio(
    monkeypatch,
):
    filas = [
        registro(),
        {
            **registro(titulo="INGENIERO CIVIL"),
            "nombreareaconocimiento": "Ingeniería de Sistemas",
        },
        registro(municipio="Acacías"),
        registro(titulo="ARQUITECTO"),
    ]
    monkeypatch.setattr(
        programas_service, "consultar_dataset", Mock(return_value=filas)
    )
    monkeypatch.setattr(
        programas_service, "obtener_municipios_departamento", Mock(return_value=set())
    )
    r = programas_service.consultar_programas_superior_service(
        municipio="Villavicencio", texto="Ingeniería de Sistemas"
    )
    assert len(r["datos"]["lista_oferta"]) == 1
    assert r["datos"]["lista_oferta"][0]["titulo_obtenido"] == "INGENIERO DE SISTEMAS"
    r = programas_service.consultar_programas_superior_service(texto="Arquitectura")
    assert r["datos"]["lista_oferta"][0]["titulo_obtenido"] == "ARQUITECTO"


def test_filtro_inactivos_y_nombres_no_encontrados_no_inventan_resultados(monkeypatch):
    monkeypatch.setattr(
        programas_service,
        "consultar_dataset",
        Mock(return_value=[registro(), registro(estado="Inactivo")]),
    )
    monkeypatch.setattr(
        programas_service, "obtener_municipios_departamento", Mock(return_value=set())
    )
    r = programas_service.consultar_programas_superior_service(
        texto="Ingeniería de Sistemas", estado="Inactivo"
    )
    assert [f["estado"] for f in r["datos"]["lista_oferta"]] == ["Inactivo"]
    r = programas_service.consultar_programas_superior_service(
        texto="Programa inexistente"
    )
    assert r["datos"]["lista_oferta"] == []
    assert "No encontré" in r["respuesta_corta"]
    assert r["datos"]["total_programas_unicos"] is None


def test_nombre_solo_busca_nacional_y_nombre_con_ciudad_filtra(monkeypatch):
    monkeypatch.setattr(
        programas_service,
        "consultar_dataset",
        Mock(return_value=[registro(titulo="ARQUITECTO")]),
    )
    monkeypatch.setattr(
        programas_service, "obtener_municipios_departamento", Mock(return_value=set())
    )
    monkeypatch.setattr(
        consulta_service,
        "detectar_territorio",
        Mock(side_effect=[(None, None), ("Meta", "Villavicencio")]),
    )
    with TestClient(main.app) as cliente:
        for pregunta, ciudad in [
            ("Arquitectura", None),
            ("Arquitectura en Villavicencio", "Villavicencio"),
        ]:
            r = cliente.post("/chat", json={"pregunta": pregunta})
            assert r.status_code == 200
            d = r.json()["datos"]["detalle_consulta"]
            assert d["territorio"]["municipio"] == ciudad
            assert d["lista_oferta"][0]["estado"] == "Activo"


@pytest.mark.parametrize(
    "pregunta", ["Deserción en Meta", "Repitencia en Meta", "Cobertura en Meta"]
)
def test_indicadores_no_se_confunden_con_nombres_de_programas(monkeypatch, pregunta):
    programas = Mock(side_effect=AssertionError("Un indicador no es un programa"))
    monkeypatch.setattr(
        consulta_service, "consultar_programas_superior_service", programas
    )
    monkeypatch.setattr(
        consulta_service, "detectar_territorio", Mock(return_value=("Meta", None))
    )
    monkeypatch.setattr(
        consulta_service,
        "buscar_en_dataset",
        Mock(return_value={"dataset": {}, "total_resultados": 0, "resultados": []}),
    )
    monkeypatch.setattr(
        consulta_service,
        "construir_respuesta_ciudadana",
        Mock(return_value={"respuesta_corta": "Indicadores disponibles."}),
    )
    r = consulta_service.resolver_consulta_ciudadana(pregunta)
    assert r["dataset_usado"] == "estadisticas_municipio"
    programas.assert_not_called()
