"""Búsqueda de colegios por nombre o código, sin seleccionar coincidencias ambiguas."""

import re
from config import DATASETS
from services.directorio_colegios import consultar_directorio_vigente
from services.establecimientos_service import construir_lista_establecimientos


def extraer_busqueda_dane(pregunta, departamento=None, municipio=None):
    codigo = re.search(r"\b\d{8,15}\b", pregunta)
    if codigo:
        return None, codigo.group()
    entre_comillas = re.search(r'"([^"\n]+)"|«([^»\n]+)»', pregunta)
    if entre_comillas:
        return next(g for g in entre_comillas.groups() if g), None
    partes = re.split(r"c[oó]digo\s+dane", pregunta, maxsplit=1, flags=re.I)
    nombre = partes[-1] if len(partes) > 1 else ""
    nombre = re.sub(
        r"^\s*(?:(?:del|de|el|la|un|una|colegio|escuela|establecimiento)\s+)+",
        "",
        nombre,
        flags=re.I,
    )
    for territorio in (municipio, departamento):
        if territorio:
            nombre = re.sub(
                r"\s+(?:en|de)\s+" + re.escape(territorio) + r"\s*[?.]*$",
                "",
                nombre,
                flags=re.I,
            )
    return nombre.strip(' ?.:,"«»') or None, None


def consultar_codigo_dane_service(
    nombre=None, codigo=None, departamento=None, municipio=None
):
    if not nombre and not codigo:
        raise ValueError("Escribe el nombre del colegio o su código DANE.")
    registros, anio = consultar_directorio_vigente(
        departamento, municipio, nombre=nombre, codigo=codigo
    )
    colegios = construir_lista_establecimientos(
        registros, "nombre_establecimiento", "sector", None, None, "codigo_dane"
    )
    if len(colegios) == 1:
        colegio = colegios[0]
        codigo_encontrado = colegio["codigo_establecimiento"]
        respuesta = (
            f"El código DANE de {colegio['nombre_establecimiento']} es {codigo_encontrado}."
            if codigo_encontrado
            else f"La fuente no informa un código DANE para {colegio['nombre_establecimiento']}."
        )
    elif colegios:
        respuesta = f"Encontré {len(colegios)} colegios que coinciden con tu búsqueda. Selecciona el colegio para consultar su código DANE; puedes precisar el nombre o la ciudad."
    else:
        respuesta = f"No encontré un colegio con esos datos en la vigencia {anio}. Prueba con otra parte del nombre o revisa la ciudad."
    return {
        "tipo_consulta": "codigo_dane",
        "respuesta_corta": respuesta,
        "datos": {
            "coincidencias_dane": colegios,
            "vigencia_mas_reciente": anio,
            "total_establecimientos_unicos": len(colegios),
            "consulta_completa": True,
        },
        "fuentes_usadas": [DATASETS["establecimientos_educativos"]],
        "limitaciones": [
            f"Datos del MEN para {anio}; el código identifica el establecimiento, no necesariamente cada sede."
        ],
    }
