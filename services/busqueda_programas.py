"""Extrae el nombre consultado y lo relaciona con títulos e instituciones publicados."""

import re
from utils.normalizacion import normalizar_texto


def extraer_nombre_programa(pregunta, municipio=None, departamento=None):
    citado = re.search(r'"([^"\n]+)"|«([^»\n]+)»', pregunta)
    if citado:
        return next(g for g in citado.groups() if g)
    p = normalizar_texto(pregunta)
    for territorio in (municipio, departamento):
        if territorio:
            p = re.sub(
                r"\b(?:(?:en|de)\s+)?"
                + re.escape(normalizar_texto(territorio))
                + r"\b",
                "",
                p,
            )
    p = p.replace("educacion superior", "")
    genericas = set(
        "que cuales cual hay tiene tienen es esta estan se reporta reportan ofrecen ofrece buscar busca quiero saber conocer sobre informacion consultar consulta programa programas carrera carreras titulo titulos universidad universidades instituciones estado activo activos activa activas inactivo inactivos inactiva inactivas nacional colombia nivel academico academicos por favor del el la los las un una".split()
    )
    palabras = [palabra for palabra in p.split() if palabra not in genericas]
    texto = " ".join(palabras).strip()
    return (
        texto
        if texto and texto not in {"en", "de", "superior", "oferta", "oferta academica"}
        else None
    )


def nombre_posible(pregunta):
    p = normalizar_texto(pregunta)
    return (
        1 <= len(p.split()) <= 7
        and not any(
            palabra in p.split()
            for palabra in (
                "escribe",
                "receta",
                "poema",
                "traduce",
                "cuenta",
                "clima",
                "noticias",
                "pelicula",
                "chiste",
                "hola",
            )
        )
        and not p.startswith(("como ", "por que ", "cuando ", "quien "))
    )


def coincide_nombre(texto, valores):
    raices = {
        "ingenieria": "ingenier",
        "licenciatura": "licenciad",
        "administracion": "administra",
        "contaduria": "contad",
        "enfermeria": "enfermer",
        "psicologia": "psicolog",
        "biologia": "biolog",
        "medicina": "medic",
    }
    raices.update(
        {
            "arquitectura": "arquitect",
            "derecho": "abog",
            "odontologia": "odontolog",
            "economia": "econom",
            "diseno": "disen",
        }
    )
    tokens = [
        raices.get(palabra, palabra)
        for palabra in normalizar_texto(texto).split()
        if palabra not in {"de", "en", "del", "la", "el", "los", "las", "y"}
    ]
    return bool(tokens) and any(
        all(
            any(p.startswith(token) for p in normalizar_texto(valor).split())
            for token in tokens
        )
        for valor in valores
        if valor
    )
