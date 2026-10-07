"""Orientación determinista del alcance informativo; no genera opiniones."""

import re
from utils.normalizacion import normalizar_texto


def requiere_orientacion(pregunta: str) -> bool:
    # Un nombre de colegio entre comillas no es una petición ideológica.
    texto = re.sub(r'"[^"\n]*"|«[^»\n]*»', "", pregunta)
    p = normalizar_texto(texto)
    opinion = (
        "opina",
        "opinas",
        "opinion",
        "opiniones",
        "argumenta",
        "argumentos",
        "defiende",
        "convenceme",
        "debate",
        "ideologia",
        "ideologico",
        "justifica",
        "ensayo",
        "crees que",
        "deberia",
        "demuestra que",
        "por que",
        "a favor de",
        "en contra de",
        "como funciona",
        "que es",
        "capitalismo",
        "socialismo",
        "comunismo",
        "neoliberalismo",
    )
    if any(re.search(r"\b" + re.escape(frase) + r"\b", p) for frase in opinion):
        return True
    if re.search(r"\b(mejor|mejores|peor|peores)\b", p) and not any(
        dato in p
        for dato in ("cobertura", "matricula", "tasa", "porcentaje", "indicador")
    ):
        return True
    if re.search(r"\b(explica|explicame)\b", p):
        return not any(
            frase in p
            for frase in ("datos", "registros", "indicador", "vigencia", "codigo dane")
        )
    return False


def orientar(pregunta: str, texto: str | None = None):
    return {
        "pregunta_recibida": pregunta,
        "intencion_detectada": "orientacion_informativa",
        "dataset_usado": None,
        "total_resultados": None,
        "respuesta_ciudadana": {
            "respuesta_corta": texto
            or (
                "EducaDatos presenta información de las fuentes oficiales: colegios, códigos DANE, "
                "educación superior, bachilleres, ICETEX e indicadores educativos. "
                "Las API no permiten responder con opiniones, argumentos ideológicos o explicaciones "
                "de por qué ocurre un fenómeno. Puedes reformular tu búsqueda indicando qué dato "
                "quieres conocer y el municipio o departamento."
            ),
            "resultados_muestra": [],
            "limitaciones": [],
            "sugerencias_de_siguiente_pregunta": [
                "Colegios en Villavicencio",
                'Código DANE del colegio "Academia Militar José Antonio Páez" en Villavicencio',
                "¿Cuántos bachilleres se reportan en Meta?",
            ],
        },
        "resultados": {},
    }
