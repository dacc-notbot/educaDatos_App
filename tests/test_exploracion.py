from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest

import main
from services import (
    consulta_service,
    codigo_dane_service,
    directorio_colegios,
    router_api,
)
from services.adaptador_api import adaptar_servicio_para_app


@pytest.mark.parametrize(
    "pregunta",
    [
        "¿Qué opinas de los colegios privados?",
        "Defiende el socialismo en la educación",
        "Argumenta que ICETEX es malo",
        "¿Por qué hay deserción en Meta?",
        "Explícame cómo funciona ICETEX",
        "Escribe un ensayo sobre la educación",
        "¿Son mejores los colegios privados?",
        "Escribe una receta de cocina",
    ],
)
def test_orientacion_no_descarga_fuentes_ni_inventa_datos(monkeypatch, pregunta):
    no_consultar = Mock(
        side_effect=AssertionError("Una opinión no requiere descargar datos")
    )
    monkeypatch.setattr(consulta_service, "detectar_territorio", no_consultar)
    with TestClient(main.app) as cliente:
        r = cliente.post("/chat", json={"pregunta": pregunta})
    assert r.status_code == 200
    d = r.json()
    assert d["datos"]["intencion_detectada"] == "orientacion_informativa"
    assert d["datos"]["total_resultados"] is None
    assert d["fuentes"] == [] and d["datos"]["colecciones"] == []
    assert "reformular" in d["respuesta"]
    assert len(d["datos"]["sugerencias_de_siguiente_pregunta"]) == 3
    no_consultar.assert_not_called()


@pytest.mark.parametrize(
    "pregunta",
    [
        "Explica qué muestran los datos de ICETEX en Meta",
        'Colegios llamados "Socialismo" en Villavicencio',
        "¿Qué municipio tiene mejor cobertura educativa?",
        "Colegios en Villavicencio",
    ],
)
def test_informacion_de_fuentes_no_se_confunde_con_opiniones(pregunta):
    from services.orientacion_service import requiere_orientacion

    assert not requiere_orientacion(pregunta)


@pytest.mark.parametrize(
    "pregunta,nombre,codigo",
    [
        ('Código DANE del colegio "San José" en Villavicencio', "San José", None),
        (
            "¿Cuál es el código DANE del colegio San José en Villavicencio?",
            "San José",
            None,
        ),
        ("Colegio con código DANE 350001002571", None, "350001002571"),
        ("Código DANE", None, None),
    ],
)
def test_extraer_nombre_o_codigo_sin_perder_tildes(pregunta, nombre, codigo):
    assert codigo_dane_service.extraer_busqueda_dane(
        pregunta, "Meta", "Villavicencio"
    ) == (nombre, codigo)


def fila(codigo, nombre="San José", municipio="Villavicencio"):
    return {
        "codigo_dane": codigo,
        "nombre_establecimiento": nombre,
        "municipio": municipio,
        "departamento": "Meta",
        "sector": "OFICIAL",
        "a_o": "2025",
    }


def test_busqueda_dane_nacional_no_elije_una_coincidencia_ambigua(monkeypatch):
    descargar = Mock(
        return_value=(
            [fila("111111111111"), fila("222222222222", municipio="Acacías")],
            2025,
        )
    )
    monkeypatch.setattr(codigo_dane_service, "consultar_directorio_vigente", descargar)
    r = codigo_dane_service.consultar_codigo_dane_service(nombre="San José")
    assert "2 colegios" in r["respuesta_corta"] and "Selecciona" in r["respuesta_corta"]
    assert [c["municipio"] for c in r["datos"]["coincidencias_dane"]] == [
        "Villavicencio",
        "Acacías",
    ]
    descargar.assert_called_once_with(None, None, nombre="San José", codigo=None)


def test_dane_faltante_no_se_inventa_y_sin_coincidencias_no_hay_codigo(monkeypatch):
    descargar = Mock(side_effect=[([fila("")], 2025), ([], 2025)])
    monkeypatch.setattr(codigo_dane_service, "consultar_directorio_vigente", descargar)
    assert (
        "no informa un código DANE"
        in codigo_dane_service.consultar_codigo_dane_service(nombre="San José")[
            "respuesta_corta"
        ]
    )
    assert (
        "No encontré"
        in codigo_dane_service.consultar_codigo_dane_service(nombre="San José")[
            "respuesta_corta"
        ]
    )


def test_nombres_con_tildes_y_codigo_se_filtran_en_la_fuente(monkeypatch):
    descargar = Mock(side_effect=[[{"vigencia": "2025"}], [{"total": "0"}]])
    monkeypatch.setattr(directorio_colegios, "consultar_dataset", descargar)
    directorio_colegios.consultar_directorio_vigente(
        None, None, nombre="San JOSÉ", codigo="350001002571"
    )
    consulta = descargar.call_args.kwargs["params_extra"]["$where"]
    assert "codigo_dane = 350001002571" in consulta and "'JOSE'" in consulta
    assert "replace(" in consulta and "'É', 'E'" in consulta


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"nombre": "!!"},
        {"nombre": " "},
        {"codigo": "x' OR 1=1"},
        {"codigo": "1" * 16},
    ],
)
def test_modelo_dane_rechaza_entradas_invalidas_antes_de_consultar(
    monkeypatch, payload
):
    descargar = Mock(side_effect=AssertionError("No consultar entradas inválidas"))
    monkeypatch.setattr(router_api, "consultar_codigo_dane_service", descargar)
    with TestClient(main.app) as cliente:
        assert cliente.post("/colegios/codigo-dane", json=payload).status_code == 422
    descargar.assert_not_called()


def test_chat_y_ruta_dane_conservan_codigo_y_coleccion(monkeypatch):
    monkeypatch.setattr(
        codigo_dane_service,
        "consultar_directorio_vigente",
        Mock(return_value=([fila("350001002571")], 2025)),
    )
    monkeypatch.setattr(
        consulta_service,
        "detectar_territorio",
        Mock(return_value=("Meta", "Villavicencio")),
    )
    with TestClient(main.app) as cliente:
        chat = cliente.post(
            "/chat",
            json={"pregunta": 'Código DANE del colegio "San José" en Villavicencio'},
        )
        directo = cliente.post(
            "/colegios/codigo-dane",
            json={"nombre": "San José", "municipio": "Villavicencio"},
        )
    for r in (chat, directo):
        assert r.status_code == 200
        assert "350001002571" in r.json()["respuesta"]
        coleccion = r.json()["datos"]["colecciones"][0]
        assert coleccion["es_muestra"] is False
        assert coleccion["filas"][0]["codigo_establecimiento"] == "350001002571"


def test_colecciones_distinguen_muestras_resumenes_y_recomendaciones_sin_perder_ceros():
    r = adaptar_servicio_para_app(
        {
            "respuesta_corta": "ICETEX",
            "datos": {
                "muestra_icetex": [{"institucion": "A", "creditos": 0}],
                "instituciones_frecuentes": {"A": 0, "B": 2},
            },
            "recomendaciones_generales": ["Revisar cobertura."],
        }
    )
    colecciones = r["datos"]["colecciones"]
    assert len(colecciones) == 3 and all(c["es_muestra"] for c in colecciones)
    assert any(c["filas"][0].get("creditos") == 0 for c in colecciones)
    assert any(c["filas"][0].get("cantidad") == 0 for c in colecciones)
