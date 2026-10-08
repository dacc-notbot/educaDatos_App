from unittest.mock import Mock

import pytest

from services import procedencia_oferta_service as procedencia
from services import programas_service
from services.resumen_oferta_service import construir_resumen_oferta, ciclo_publicado


def oferta(estado="Activo", modalidad="Presencial", nivel="Universitaria", **extra):
    return {
        "nombreprograma": "Meta",
        "codigoprograma": "50",
        "nombredepartprograma": "Meta",
        "nombremunicipioprograma": "Villavicencio",
        "nombreinstitucion": "Universidad A",
        "nombretituloobtenido": "INGENIERO DE SISTEMAS",
        "nombreestadoprograma": estado,
        "nombrenivelformacion": nivel,
        "nombrenivelacademico": "Pregrado" if nivel == "Universitaria" else "Posgrado",
        "nombremetodologia": modalidad,
        **extra,
    }


@pytest.fixture(autouse=True)
def metadatos_sin_red(monkeypatch):
    monkeypatch.setattr(procedencia, "obtener_metadatos_oferta", Mock(return_value={}))
    monkeypatch.setattr(programas_service, "obtener_municipios_departamento", Mock(return_value=set()))


def consultar(monkeypatch, filas, **filtros):
    monkeypatch.setattr(programas_service, "consultar_dataset", Mock(return_value=filas))
    return programas_service.consultar_programas_superior_service(**filtros)["datos"]


def test_resumen_y_listado_cuentan_la_misma_unidad_y_conservan_modalidades_y_estados(monkeypatch):
    filas = [oferta(), oferta(), oferta(estado="Inactivo"), oferta(modalidad="Virtual"), oferta(nivel="Maestría")]
    datos = consultar(monkeypatch, filas, departamento="Meta")
    resumen = datos["resumen_oferta"]
    assert resumen["unidad_conteo"] == "ofertas publicadas"
    assert resumen["total_ofertas"] == len(datos["lista_oferta"]) == 4
    assert datos["total_programas_unicos"] is None
    nivel = next(fila for fila in resumen["por_nivel"] if fila["nivel"] == "Universitaria")
    assert nivel == {"nivel": "Universitaria", "total": 3, "activos": 2, "inactivos": 1, "sin_estado": 0}
    modalidad = next(fila for fila in resumen["por_modalidad"] if fila["modalidad"] == "Presencial")
    assert modalidad["total"] == 3 and modalidad["activos"] == 2 and modalidad["inactivos"] == 1
    assert {fila["ciclo"]: fila["total"] for fila in resumen["por_ciclo"]} == {"Pregrado": 3, "Posgrado": 1}
    assert sum(fila["conteo"] for fila in datos["distribucion_estado"]) == 4


def test_deduplicacion_preserva_departamento_sede_e_identidad_fiable(monkeypatch):
    filas = [
        oferta(nombredepartprograma="Departamento A", nombresede="Norte"),
        oferta(nombredepartprograma="Departamento B", nombresede="Norte"),
        oferta(nombredepartprograma="Departamento A", nombresede="Sur"),
    ]
    # Mantiene la simulación de la inconsistencia existente por departamento.
    for fila in filas:
        fila["nombreprograma"] = fila["nombredepartprograma"]
    datos = consultar(monkeypatch, filas)
    assert len(datos["lista_oferta"]) == 3
    filas = [oferta(nombreprograma="Ingeniería", codigoprograma=codigo) for codigo in ["100", "200"]]
    datos = consultar(monkeypatch, filas)
    assert len(datos["lista_oferta"]) == 2
    assert datos["total_programas_unicos"] == 2
    assert {fila["codigo_programa"] for fila in datos["lista_oferta"]} == {"100", "200"}


def test_instituciones_completas_y_niveles_sin_top10(monkeypatch):
    filas = [oferta(nombreinstitucion=f"Institución {n}", nombrenivelformacion=f"Nivel {n}") for n in range(14)]
    datos = consultar(monkeypatch, filas)
    resumen = datos["resumen_oferta"]
    assert len(resumen["instituciones"]) == len(datos["instituciones_frecuentes"]) == 14
    assert len(resumen["por_nivel"]) == len(datos["distribucion_nivel"]) == 14
    assert sum(fila["total_ofertas"] for fila in resumen["instituciones"]) == 14
    for institucion in resumen["instituciones"]:
        assert institucion["activos"] == institucion["total_ofertas"] == 1
        assert institucion["modalidades"][0]["modalidad"] == "Presencial"
        assert institucion["niveles"] and institucion["ciclos"]


def test_desconocidos_no_se_asignan_a_activos_o_inactivos(monkeypatch):
    filas = [oferta(estado=None, modalidad=None, nivel=None), oferta(estado="En trámite", modalidad="Mixta")]
    filas[0]["nombrenivelacademico"] = None
    datos = consultar(monkeypatch, filas)
    resumen = datos["resumen_oferta"]
    assert {fila["estado"] for fila in resumen["por_estado"]} == {"Sin información", "En trámite"}
    assert sum(fila["activos"] for fila in resumen["por_nivel"]) == 0
    assert sum(fila["sin_estado"] for fila in resumen["por_nivel"]) == 2
    assert any(fila["modalidad"] == "Sin información" for fila in resumen["por_modalidad"])
    assert any(fila["ciclo"] == "Sin información" for fila in resumen["por_ciclo"])
    assert {fila["modalidad"] for fila in datos["lista_oferta"]} == {"Sin información", "Mixta"}


def test_programas_nacionales_sin_filtros_y_cero_resultados(monkeypatch):
    datos = consultar(monkeypatch, [oferta()])
    assert datos["resumen_oferta"]["total_ofertas"] == 1
    datos = consultar(monkeypatch, [oferta()], texto="Programa que no existe")
    assert datos["lista_oferta"] == []
    assert datos["resumen_oferta"]["total_ofertas"] == 0
    assert datos["resumen_oferta"]["instituciones"] == []


def test_vigencia_explicita_selecciona_solo_registro_mas_reciente(monkeypatch):
    datos = consultar(monkeypatch, [oferta(a_o="2024"), oferta(a_o="2025", estado="Inactivo")])
    assert datos["procedencia_oferta"]["anio_registro"] == 2025
    assert datos["resumen_oferta"]["total_ofertas"] == 1
    assert datos["lista_oferta"][0]["estado"] == "Inactivo"


def test_no_convierte_fecha_creacion_acreditacion_o_modificacion_portal_en_anio(monkeypatch):
    monkeypatch.setattr(procedencia, "obtener_metadatos_oferta", Mock(return_value={"rowsUpdatedAt": 1736877803, "viewLastModified": 1779130101}))
    datos = consultar(monkeypatch, [oferta(fechacreacion="17/04/2006", aniosacreditados="7")])
    fuente = datos["procedencia_oferta"]
    assert fuente["anio_registro"] is None
    assert fuente["fecha_actualizacion"] == "2025-01-14"
    assert "14 de enero de 2025" in fuente["descripcion_ciudadana"]
    assert "La fuente no informa el año de registro" in fuente["descripcion_ciudadana"]
    assert "2026" not in fuente["descripcion_ciudadana"]


def test_metadato_sin_fecha_datos_no_usa_fecha_portal_como_suplente(monkeypatch):
    monkeypatch.setattr(procedencia, "obtener_metadatos_oferta", Mock(return_value={"viewLastModified": 1779130101}))
    fuente = procedencia.construir_procedencia_oferta()
    assert fuente["fecha_actualizacion"] is None
    assert fuente["anio_registro"] is None


@pytest.mark.parametrize("nivel,ciclo", [("Universitaria", "Pregrado"), ("Tecnológica", "Pregrado"), ("Formación técnica profesional", "Pregrado"), ("Especialización universitaria", "Posgrado"), ("Maestría", "Posgrado"), ("Doctorado", "Posgrado"), ("Curso sin categoría", "Sin información")])
def test_ciclo_reconoce_solo_niveles_inequivocos(nivel, ciclo):
    assert ciclo_publicado(None, nivel) == ciclo


def test_resumen_no_silencia_institucion_no_informada():
    resumen = construir_resumen_oferta([{"nivel": "Maestría", "estado": "Activo", "ciclo": "Posgrado"}])
    assert resumen["instituciones"][0]["institucion"] == "Sin información"
    assert resumen["por_modalidad"][0]["modalidad"] == "Sin información"
