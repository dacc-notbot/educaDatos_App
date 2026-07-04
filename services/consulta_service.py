from typing import Any, Dict, Optional, Tuple, List

try:
    from config import (
        DEFAULT_ANALYTIC_LIMIT,
        DEFAULT_LIMIT,
        MAX_LIMIT,
        MIN_LIMIT_MUNICIPAL,
        MIN_LIMIT_DEPARTAMENTAL,
    )
except Exception:
    DEFAULT_ANALYTIC_LIMIT = 100_000
    DEFAULT_LIMIT = 100_000
    MAX_LIMIT = 1_000_000
    MIN_LIMIT_MUNICIPAL = 100_000
    MIN_LIMIT_DEPARTAMENTAL = 500_000

from services.socrata_service import (
    buscar_en_dataset,
    normalizar_texto,
)

from services.territorio_service import detectar_territorio_nacional
from services.respuesta_service import construir_respuesta_ciudadana

from services.clustering_service import (
    consultar_cluster_municipio_service,
    consultar_clusters_municipios_service,
    buscar_municipios_similares_service,
    generar_recomendaciones_municipio_service,
)

from services.cruce_service import analizar_transito_educativo_service
from services.establecimientos_service import consultar_establecimientos_educativos_service
from services.programas_service import consultar_programas_superior_service
from services.bachilleres_service import consultar_bachilleres_service
from services.icetex_service import consultar_icetex_service
from services.diagnostico_service import diagnostico_territorial_educativo_service


# ============================================================
# Utilidades generales
# ============================================================

def resolver_limite_consulta(
    departamento: Optional[str],
    municipio: Optional[str],
    limit: Optional[int],
) -> int:
    """
    Define límites amplios para consultas nacionales, departamentales o municipales.
    Evita que un diagnóstico o cruce quede sesgado por consultar pocos registros.
    """
    try:
        limit_solicitado = int(limit) if limit is not None else DEFAULT_ANALYTIC_LIMIT
    except (TypeError, ValueError):
        limit_solicitado = DEFAULT_ANALYTIC_LIMIT or DEFAULT_LIMIT

    if departamento and not municipio:
        limit_final = max(limit_solicitado, MIN_LIMIT_DEPARTAMENTAL)
    elif municipio:
        limit_final = max(limit_solicitado, MIN_LIMIT_MUNICIPAL)
    else:
        limit_final = max(limit_solicitado, DEFAULT_ANALYTIC_LIMIT)

    return min(limit_final, MAX_LIMIT)


def contiene_alguna(texto: str, palabras: List[str]) -> bool:
    texto_norm = normalizar_texto(texto)

    for palabra in palabras:
        if normalizar_texto(palabra) in texto_norm:
            return True

    return False


def numero_seguro(valor: Any, defecto: int = 0) -> int:
    if valor is None:
        return defecto

    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return defecto


def total_cruce_seguro(resumen_por_fuente: Dict[str, Any]) -> int:
    """
    Calcula un total orientativo para el cruce sin romperse por valores None.
    """
    total = 0

    for fuente in resumen_por_fuente.values():
        if not isinstance(fuente, dict):
            continue

        candidatos = [
            fuente.get("total_registros"),
            fuente.get("total_registros_vigencia"),
            fuente.get("total_programas_unicos"),
            fuente.get("total_bachilleres_aproximado"),
            fuente.get("total_creditos_o_beneficiarios_aproximado"),
        ]

        for candidato in candidatos:
            if candidato is not None:
                total += numero_seguro(candidato)
                break

    return total


# ============================================================
# Detección de intención
# ============================================================

def clasificar_intencion(pregunta: str) -> Dict[str, Any]:
    """
    Clasifica una pregunta ciudadana con reglas transparentes.
    No usa IA generativa; enruta hacia servicios especializados.
    """
    p = normalizar_texto(pregunta)

    # --------------------------------------------------------
    # Diagnóstico territorial integral
    # --------------------------------------------------------
    if any(palabra in p for palabra in [
        "diagnostico",
        "diagnóstico",
        "radiografia",
        "radiografía",
        "panorama educativo",
        "situacion educativa",
        "situación educativa",
        "estado educativo",
        "analisis educativo",
        "análisis educativo",
        "analisis integral",
        "análisis integral",
        "reporte educativo",
        "informe educativo",
        "como esta la educacion",
        "cómo está la educación",
        "como esta educativamente",
        "cómo está educativamente",
    ]):
        return {
            "tipo_consulta": "diagnostico_territorial",
            "accion": "diagnostico_territorial_educativo",
            "dataset_key": "multiples_datasets",
            "intencion": "diagnostico_territorial",
            "explicacion": (
                "La pregunta busca un diagnóstico educativo territorial amplio; "
                "se integrarán establecimientos, programas, tránsito educativo, "
                "municipios similares y recomendaciones exploratorias."
            ),
        }

    # --------------------------------------------------------
    # Tránsito educativo: bachilleres + superior + financiación
    # --------------------------------------------------------
    if es_pregunta_transito_educativo(pregunta):
        return {
            "tipo_consulta": "cruce_datasets",
            "accion": "transito_educativo",
            "dataset_key": "multiples_datasets",
            "intencion": "analizar_transito_educativo",
            "explicacion": (
                "La pregunta busca relacionar bachilleres, educación superior "
                "y/o financiación educativa; se usará un cruce exploratorio de datasets."
            ),
        }

    # --------------------------------------------------------
    # Municipios similares / agrupación estadística
    # --------------------------------------------------------
    if any(palabra in p for palabra in [
        "municipios similares",
        "municipios parecidos",
        "municipios se parecen",
        "municipios que se parecen",
        "se parecen",
        "se parece",
        "parecidos a",
        "similares a",
        "similar a",
        "comparables con",
        "municipios comparables",
        "territorios similares",
        "condiciones educativas similares",
        "condicion educativa similar",
        "condición educativa similar",
        "comportamiento educativo similar",
        "municipios con condiciones educativas similares",
        "municipios con comportamiento educativo similar",
    ]):
        return {
            "tipo_consulta": "analitica_clustering",
            "accion": "municipios_similares",
            "dataset_key": "estadisticas_municipio",
            "intencion": "buscar_municipios_similares",
            "explicacion": (
                "La pregunta busca municipios con comportamiento educativo similar; "
                "se usará una agrupación estadística exploratoria y distancia entre indicadores."
            ),
        }

    if any(palabra in p for palabra in [
        "recomendacion",
        "recomendaciones",
        "sugerencias",
        "que hacer",
        "qué hacer",
        "acciones educativas",
        "estrategias educativas",
        "mejorar",
        "priorizar",
    ]):
        return {
            "tipo_consulta": "analitica_clustering",
            "accion": "recomendaciones_municipio",
            "dataset_key": "estadisticas_municipio",
            "intencion": "generar_recomendaciones_municipio",
            "explicacion": (
                "La pregunta busca recomendaciones exploratorias a partir del perfil "
                "educativo municipal y su grupo de municipios similares."
            ),
        }

    if any(palabra in p for palabra in [
        "cluster",
        "clúster",
        "grupo educativo",
        "grupo estadistico",
        "grupo estadístico",
        "grupo describe",
        "grupo describe mejor",
        "que grupo describe",
        "qué grupo describe",
        "que grupo describe mejor",
        "qué grupo describe mejor",
        "perfil educativo",
        "en que grupo",
        "en qué grupo",
        "grupo pertenece",
        "clasificacion educativa",
        "clasificación educativa",
        "agrupacion",
        "agrupación",
    ]):
        return {
            "tipo_consulta": "analitica_clustering",
            "accion": "perfil_cluster_municipio",
            "dataset_key": "estadisticas_municipio",
            "intencion": "consultar_grupo_educativo_municipio",
            "explicacion": (
                "La pregunta busca conocer el grupo de municipios con comportamiento "
                "educativo similar al que pertenece un municipio."
            ),
        }

    # --------------------------------------------------------
    # Establecimientos educativos
    # --------------------------------------------------------
    if any(palabra in p for palabra in [
        "colegio",
        "colegios",
        "escuela",
        "escuelas",
        "institucion educativa",
        "institución educativa",
        "establecimiento educativo",
        "establecimientos educativos",
        "sede educativa",
        "sedes educativas",
        "privado",
        "privados",
        "oficial",
        "oficiales",
    ]):
        return {
            "dataset_key": "establecimientos_educativos",
            "intencion": "buscar_establecimientos_educativos",
            "explicacion": "La pregunta busca colegios, sedes o establecimientos educativos.",
        }

    # --------------------------------------------------------
    # Programas de educación superior
    # --------------------------------------------------------
    if any(palabra in p for palabra in [
        "universidad",
        "universidades",
        "educacion superior",
        "educación superior",
        "pregrado",
        "posgrado",
        "carrera",
        "carreras",
        "programa universitario",
        "programas universitarios",
        "programa profesional",
        "programas profesionales",
        "programas academicos",
        "programas académicos",
        "oferta academica",
        "oferta académica",
        "que universidades ofrecen",
        "qué universidades ofrecen",
        "universidades ofrecen",
        "programas de ingenieria",
        "programas de ingeniería",
        "ingenieria",
        "ingeniería",
        "licenciatura",
        "medicina",
        "derecho",
        "administracion",
        "administración",
        "contaduria",
        "contaduría",
        "enfermeria",
        "enfermería",
        "psicologia",
        "psicología",
    ]):
        return {
            "dataset_key": "programas_superior",
            "intencion": "buscar_programas_educacion_superior",
            "explicacion": "La pregunta busca oferta de educación superior.",
        }

    # --------------------------------------------------------
    # Bachilleres
    # --------------------------------------------------------
    if any(palabra in p for palabra in [
        "bachiller",
        "bachilleres",
        "graduados",
        "egresados",
        "grado once",
        "grado 11",
        "terminan el colegio",
        "educacion media",
        "educación media",
    ]):
        return {
            "dataset_key": "bachilleres",
            "intencion": "consultar_bachilleres",
            "explicacion": (
                "La pregunta está relacionada con bachilleres o egresados de educación media."
            ),
        }

    # --------------------------------------------------------
    # ICETEX
    # --------------------------------------------------------
    if any(palabra in p for palabra in [
        "icetex",
        "credito educativo",
        "crédito educativo",
        "creditos educativos",
        "créditos educativos",
        "financiacion",
        "financiación",
        "prestamo educativo",
        "préstamo educativo",
        "renovacion credito",
        "renovación crédito",
    ]):
        if "renov" in p:
            return {
                "dataset_key": "icetex_renovados",
                "intencion": "consultar_creditos_icetex_renovados",
                "explicacion": "La pregunta consulta créditos ICETEX renovados.",
            }

        return {
            "dataset_key": "icetex_otorgados",
            "intencion": "consultar_creditos_icetex_otorgados",
            "explicacion": "La pregunta consulta créditos ICETEX otorgados.",
        }

    # --------------------------------------------------------
    # Educación para el trabajo
    # --------------------------------------------------------
    if any(palabra in p for palabra in [
        "etdh",
        "educacion para el trabajo",
        "educación para el trabajo",
        "formacion para el trabajo",
        "formación para el trabajo",
        "instituto tecnico",
        "instituto técnico",
        "institucion tecnica",
        "institución técnica",
        "tecnico laboral",
        "técnico laboral",
        "formacion laboral",
        "formación laboral",
    ]):
        return {
            "dataset_key": "instituciones_etdh",
            "intencion": "buscar_instituciones_etdh",
            "explicacion": (
                "La pregunta busca instituciones de educación para el trabajo "
                "y desarrollo humano."
            ),
        }

    if any(palabra in p for palabra in [
        "curso",
        "cursos",
        "programa tecnico",
        "programa técnico",
        "programas tecnicos",
        "programas técnicos",
        "tecnico en",
        "técnico en",
        "laboral por competencias",
        "capacitacion",
        "capacitación",
    ]):
        return {
            "dataset_key": "programas_etdh",
            "intencion": "buscar_programas_etdh",
            "explicacion": (
                "La pregunta busca programas de formación técnica laboral o ETDH."
            ),
        }

    # --------------------------------------------------------
    # Primera infancia
    # --------------------------------------------------------
    if any(palabra in p for palabra in [
        "primera infancia",
        "educacion inicial",
        "educación inicial",
        "jardin",
        "jardín",
        "prejardin",
        "prejardín",
        "infancia",
        "ninos pequenos",
        "niños pequeños",
    ]):
        return {
            "dataset_key": "primera_infancia",
            "intencion": "consultar_primera_infancia",
            "explicacion": "La pregunta está relacionada con primera infancia o educación inicial.",
        }

    # --------------------------------------------------------
    # Conectividad y territorio local
    # --------------------------------------------------------
    if any(palabra in p for palabra in [
        "wifi",
        "internet",
        "conectividad",
        "zona wifi",
        "zonas wifi",
    ]):
        return {
            "dataset_key": "zonas_wifi_meta",
            "intencion": "buscar_zonas_wifi",
            "explicacion": "La pregunta busca información de conectividad o zonas wifi.",
        }

    if any(palabra in p for palabra in [
        "barrio",
        "barrios",
        "vereda",
        "veredas",
        "la ceiba",
        "comuna",
        "corregimiento",
    ]):
        return {
            "dataset_key": "barrios_veredas_villavicencio",
            "intencion": "buscar_barrios_veredas",
            "explicacion": "La pregunta busca información territorial de barrios o veredas.",
        }

    return {
        "dataset_key": "estadisticas_municipio",
        "intencion": "consultar_estadisticas_municipales",
        "explicacion": (
            "No se identificó una intención específica; se usará el dataset general "
            "de estadísticas educativas municipales."
        ),
    }


def detectar_territorio(pregunta: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Detecta departamento y municipio.

    Incluye respaldo para Bogotá porque en datos abiertos puede aparecer como:
    - Bogotá
    - Bogotá, D.C.
    - Bogotá D.C.
    """
    departamento, municipio = detectar_territorio_nacional(pregunta)

    if departamento or municipio:
        return departamento, municipio

    p = normalizar_texto(pregunta)

    if "bogota" in p or "bogota dc" in p or "bogota d c" in p:
        return "Bogotá, D.C.", "Bogotá, D.C."

    return departamento, municipio


def detectar_texto_especifico(
    pregunta: str,
    municipio: Optional[str],
    departamento: Optional[str],
) -> Optional[str]:
    """
    Extrae una palabra útil para búsqueda textual.
    No devuelve palabras genéricas como 'educación' o 'programas'.
    Tampoco devuelve municipio/departamento, porque esos se filtran aparte.
    """
    p = normalizar_texto(pregunta)

    terminos_especificos = [
        "normal superior",
        "ingenieria",
        "ingeniería",
        "licenciatura",
        "medicina",
        "derecho",
        "administracion",
        "administración",
        "contaduria",
        "contaduría",
        "enfermeria",
        "enfermería",
        "psicologia",
        "psicología",
        "sistemas",
        "agropecuaria",
        "ambiental",
        "matematica",
        "matemática",
        "lengua castellana",
        "ingles",
        "inglés",
        "pedagogia",
        "pedagogía",
        "la ceiba",
    ]

    for termino in terminos_especificos:
        if normalizar_texto(termino) in p:
            return termino

    return None


def es_texto_generico_educativo(texto: Optional[str]) -> bool:
    if not texto:
        return False

    texto_norm = normalizar_texto(texto)

    palabras_genericas = {
        "educacion",
        "educacion superior",
        "superior",
        "programa",
        "programas",
        "oferta",
        "oferta academica",
        "academica",
        "universidad",
        "universidades",
        "carrera",
        "carreras",
        "institucion",
        "instituciones",
        "ies",
    }

    return texto_norm in palabras_genericas


def detectar_sector_establecimiento(pregunta: str) -> Optional[str]:
    p = normalizar_texto(pregunta)

    if any(palabra in p for palabra in [
        "no oficial",
        "no oficiales",
        "no_oficial",
        "privado",
        "privados",
        "particular",
        "particulares",
    ]):
        return "NO_OFICIAL"

    if any(palabra in p for palabra in [
        "oficial",
        "oficiales",
        "publico",
        "publicos",
        "público",
        "públicos",
    ]):
        return "OFICIAL"

    return None


def es_pregunta_conteo_establecimientos(pregunta: str) -> bool:
    """
    Detecta preguntas donde el ciudadano quiere un número,
    no una lista detallada.
    """
    return contiene_alguna(pregunta, [
        "cuantos colegios",
        "cuántos colegios",
        "cuantos establecimientos",
        "cuántos establecimientos",
        "cantidad de colegios",
        "numero de colegios",
        "número de colegios",
        "total de colegios",
        "cuantos hay",
        "cuántos hay",
    ])


def es_pregunta_lista_establecimientos(pregunta: str) -> bool:
    """
    Detecta preguntas donde el ciudadano sí pide ver nombres
    o un listado de colegios.
    """
    return contiene_alguna(pregunta, [
        "lista de colegios",
        "listado de colegios",
        "muestrame la lista",
        "muéstrame la lista",
        "mostrar la lista",
        "ver la lista",
        "cuales son los colegios",
        "cuáles son los colegios",
        "que colegios oficiales",
        "qué colegios oficiales",
        "que colegios privados",
        "qué colegios privados",
        "que colegios no oficiales",
        "qué colegios no oficiales",
        "muestrame los colegios",
        "muéstrame los colegios",
        "mostrar colegios",
        "ver colegios",
        "nombres de colegios",
        "directorio de colegios",
    ])


def detectar_modo_respuesta_establecimientos(pregunta: str) -> str:
    """
    Define si la consulta de establecimientos debe responder con:

    - "conteo": solo resumen numérico.
    - "lista": listado detallado de colegios.

    Regla principal:
    Si el usuario pregunta "cuántos", gana modo conteo.
    Si pide explícitamente lista, nombres o "cuáles son", gana modo lista.
    """
    if es_pregunta_conteo_establecimientos(pregunta):
        return "conteo"

    if es_pregunta_lista_establecimientos(pregunta):
        return "lista"

    return "conteo"


def es_saludo_o_mensaje_general(pregunta: str) -> bool:
    p = normalizar_texto(pregunta)

    saludos = {
        "hola",
        "buenas",
        "buenos dias",
        "buenos días",
        "buenas tardes",
        "buenas noches",
        "saludos",
        "hey",
    }

    return p in {normalizar_texto(s) for s in saludos}


def es_pregunta_transito_educativo(pregunta: str) -> bool:
    p = normalizar_texto(pregunta)

    palabras_bachilleres = [
        "bachiller",
        "bachilleres",
        "egresado",
        "egresados",
        "graduado",
        "graduados",
        "educacion media",
        "educación media",
        "grado 11",
        "grado once",
    ]

    palabras_superior = [
        "educacion superior",
        "educación superior",
        "universidad",
        "universidades",
        "universitario",
        "universitaria",
        "programas",
        "programa",
        "carreras",
        "carrera",
        "ies",
        "tecnologica",
        "tecnológica",
        "pregrado",
    ]

    palabras_financiacion = [
        "icetex",
        "credito educativo",
        "crédito educativo",
        "creditos educativos",
        "créditos educativos",
        "financiacion",
        "financiación",
        "financiar",
        "apoyo financiero",
        "apoyos financieros",
        "credito",
        "crédito",
    ]

    palabras_relacion = [
        "relacion",
        "relación",
        "relacionan",
        "relaciona",
        "transito",
        "tránsito",
        "continuidad",
        "continuar",
        "acceso",
        "acceder",
        "ingresar",
        "oportunidad",
        "oportunidades",
        "pasar",
        "articular",
        "brecha",
        "brechas",
    ]

    tiene_bachilleres = contiene_alguna(p, palabras_bachilleres)
    tiene_superior = contiene_alguna(p, palabras_superior)
    tiene_financiacion = contiene_alguna(p, palabras_financiacion)
    tiene_relacion = contiene_alguna(p, palabras_relacion)

    if tiene_bachilleres and tiene_superior and tiene_relacion:
        return True

    if tiene_bachilleres and tiene_financiacion:
        return True

    if tiene_superior and tiene_financiacion and tiene_relacion:
        return True

    if "transito educativo" in p or "tránsito educativo" in p:
        return True

    return False


# ============================================================
# Respuestas estándar cuando falta territorio
# ============================================================

def respuesta_falta_territorio(
    pregunta: str,
    intencion: str,
    explicacion: str,
    dataset_usado: str,
    respuesta_corta: str,
    sugerencias: List[str],
) -> Dict[str, Any]:
    return {
        "pregunta_recibida": pregunta,
        "intencion_detectada": intencion,
        "explicacion_enrutamiento": explicacion,
        "dataset_usado": dataset_usado,
        "territorio_detectado": {
            "departamento": None,
            "municipio": None,
        },
        "texto_busqueda_usado": None,
        "total_resultados": 0,
        "respuesta_ciudadana": {
            "respuesta_corta": respuesta_corta,
            "hallazgos_principales": [
                "No se ejecutó la consulta porque no se detectó territorio suficiente.",
                "Puedes indicar un municipio o departamento para hacer el análisis.",
            ],
            "fuente_usada": {
                "dataset_key": dataset_usado,
                "nombre": "Datos abiertos educativos de Colombia",
                "url": "datos.gov.co",
                "descripcion": "Consulta ciudadana sobre fuentes educativas abiertas.",
            },
            "resultados_muestra": [],
            "limitaciones": [
                "La consulta requiere territorio para filtrar correctamente los datos."
            ],
            "sugerencias_de_siguiente_pregunta": sugerencias,
        },
        "resultados": [],
        "nota_para_gpt": "Solicita al usuario un municipio o departamento.",
    }


# ============================================================
# Servicio principal
# ============================================================

def resolver_consulta_ciudadana(
    pregunta: str,
    limit: int = DEFAULT_ANALYTIC_LIMIT,
) -> Dict[str, Any]:
    """
    Resuelve una pregunta ciudadana:
    1. Saluda u orienta si la pregunta no es de datos.
    2. Clasifica la intención.
    3. Detecta territorio.
    4. Enruta a servicios especializados.
    5. Devuelve una respuesta trazable, ciudadana y fiel a los datos.
    """
    if es_saludo_o_mensaje_general(pregunta):
        return {
            "pregunta_recibida": pregunta,
            "intencion_detectada": "saludo",
            "explicacion_enrutamiento": "El usuario envió un saludo o mensaje general.",
            "dataset_usado": None,
            "territorio_detectado": {
                "departamento": None,
                "municipio": None,
            },
            "texto_busqueda_usado": None,
            "total_resultados": 0,
            "respuesta_ciudadana": {
                "respuesta_corta": (
                    "Hola, soy EducaDatos. Puedo ayudarte a consultar datos abiertos "
                    "sobre colegios, bachilleres, educación superior, ICETEX, diagnóstico "
                    "territorial y grupos de municipios con comportamiento educativo similar."
                ),
                "hallazgos_principales": [
                    "Puedes preguntarme por un municipio o departamento.",
                    "Puedo relacionar bachilleres, oferta de educación superior e ICETEX.",
                    "También puedo generar diagnósticos educativos exploratorios y buscar municipios similares.",
                ],
                "fuente_usada": {},
                "resultados_muestra": [],
                "limitaciones": [
                    "Para consultas con datos necesito que indiques un territorio o tema educativo."
                ],
                "sugerencias_de_siguiente_pregunta": [
                    "¿Qué colegios hay en Soacha?",
                    "Haz un diagnóstico educativo de Villavicencio",
                    "¿Qué relación hay entre bachilleres, educación superior e ICETEX en Cundinamarca?",
                ],
            },
            "resultados": [],
            "nota_para_gpt": "Responder como saludo y orientar al usuario.",
        }

    clasificacion = clasificar_intencion(pregunta)
    departamento, municipio = detectar_territorio(pregunta)

    limit_analitico = resolver_limite_consulta(
        departamento=departamento,
        municipio=municipio,
        limit=limit,
    )

    # --------------------------------------------------------
    # Diagnóstico territorial
    # --------------------------------------------------------
    if clasificacion.get("tipo_consulta") == "diagnostico_territorial":
        if not departamento and not municipio:
            return respuesta_falta_territorio(
                pregunta=pregunta,
                intencion="diagnostico_territorial",
                explicacion=clasificacion["explicacion"],
                dataset_usado="multiples_datasets",
                respuesta_corta=(
                    "Puedo generar un diagnóstico educativo, pero necesito que indiques "
                    "un municipio o departamento."
                ),
                sugerencias=[
                    "Haz un diagnóstico educativo de Soacha",
                    "Haz un diagnóstico educativo de Villavicencio",
                    "Dame un panorama educativo de Cundinamarca",
                ],
            )

        resultado_diagnostico = diagnostico_territorial_educativo_service(
            departamento=departamento,
            municipio=municipio,
            limit=limit_analitico,
        )

        respuesta_ciudadana = resultado_diagnostico.get("respuesta_ciudadana", {})

        return {
            "pregunta_recibida": pregunta,
            "intencion_detectada": "diagnostico_territorial",
            "explicacion_enrutamiento": clasificacion["explicacion"],
            "dataset_usado": "multiples_datasets",
            "territorio_detectado": {
                "departamento": departamento,
                "municipio": municipio,
            },
            "texto_busqueda_usado": None,
            "total_resultados": 0,
            "respuesta_ciudadana": {
                "respuesta_corta": respuesta_ciudadana.get(
                    "respuesta_corta",
                    "Se generó un diagnóstico educativo territorial."
                ),
                "hallazgos_principales": respuesta_ciudadana.get("hallazgos_integrados", []),
                "fuente_usada": {
                    "dataset_key": "multiples_datasets",
                    "nombre": "Diagnóstico territorial educativo",
                    "url": "datos.gov.co",
                    "descripcion": "Diagnóstico exploratorio con varias fuentes educativas abiertas.",
                },
                "resultados_muestra": resultado_diagnostico.get("componentes", {}),
                "limitaciones": respuesta_ciudadana.get("limitaciones", []),
                "sugerencias_de_siguiente_pregunta": respuesta_ciudadana.get(
                    "sugerencias_de_siguiente_pregunta", []
                ),
            },
            "resultados": resultado_diagnostico,
            "nota_para_gpt": (
                "Presenta el diagnóstico como análisis exploratorio. "
                "No afirmes causalidad ni reemplaces fuentes oficiales."
            ),
        }

    # --------------------------------------------------------
    # Tránsito educativo
    # --------------------------------------------------------
    if clasificacion.get("tipo_consulta") == "cruce_datasets":
        if not departamento and not municipio:
            return respuesta_falta_territorio(
                pregunta=pregunta,
                intencion="analizar_transito_educativo",
                explicacion=clasificacion["explicacion"],
                dataset_usado="multiples_datasets",
                respuesta_corta=(
                    "Puedo analizar el tránsito educativo, pero necesito que indiques "
                    "un departamento o municipio."
                ),
                sugerencias=[
                    "¿Cómo se relacionan bachilleres, educación superior e ICETEX en Meta?",
                    "¿Qué oportunidades tienen los bachilleres de Soacha para acceder a educación superior?",
                    "¿Qué créditos ICETEX aparecen en Cundinamarca?",
                ],
            )

        resultado_cruce = analizar_transito_educativo_service(
            departamento=departamento,
            municipio=municipio,
            limit=limit_analitico,
        )

        return {
            "pregunta_recibida": pregunta,
            "intencion_detectada": "analizar_transito_educativo",
            "explicacion_enrutamiento": clasificacion["explicacion"],
            "dataset_usado": "multiples_datasets",
            "territorio_detectado": {
                "departamento": departamento,
                "municipio": municipio,
            },
            "texto_busqueda_usado": None,
            "total_resultados": total_cruce_seguro(
                resultado_cruce.get("resumen_por_fuente", {})
            ),
            "respuesta_ciudadana": {
                "respuesta_corta": resultado_cruce.get("respuesta_corta", ""),
                "hallazgos_principales": resultado_cruce.get("hallazgos_principales", []),
                "fuente_usada": {
                    "dataset_key": "multiples_datasets",
                    "nombre": "Cruce de bachilleres, educación superior e ICETEX",
                    "url": "datos.gov.co",
                    "descripcion": "Análisis exploratorio de tránsito educativo con varias fuentes abiertas.",
                },
                "resultados_muestra": resultado_cruce.get("resumen_por_fuente", {}),
                "limitaciones": resultado_cruce.get("limitaciones", []),
                "sugerencias_de_siguiente_pregunta": resultado_cruce.get(
                    "sugerencias_de_siguiente_pregunta", []
                ),
            },
            "resultados": resultado_cruce,
            "nota_para_gpt": (
                "Explica el cruce como análisis exploratorio. "
                "No afirmes causalidad. Resalta bachilleres, oferta superior e ICETEX como dimensiones conectadas."
            ),
        }

    # --------------------------------------------------------
    # Agrupación estadística / municipios similares
    # --------------------------------------------------------
    if clasificacion.get("tipo_consulta") == "analitica_clustering":
        accion = clasificacion.get("accion")

        if accion == "municipios_similares" and departamento and not municipio:
            resultado_analitico = consultar_clusters_municipios_service(
                departamento=departamento,
                max_resultados=30,
                limit=limit_analitico,
            )

            resultados = resultado_analitico.get("resultados", [])

            return {
                "pregunta_recibida": pregunta,
                "intencion_detectada": "buscar_municipios_similares",
                "explicacion_enrutamiento": clasificacion["explicacion"],
                "dataset_usado": "estadisticas_municipio",
                "territorio_detectado": {
                    "departamento": departamento,
                    "municipio": municipio,
                },
                "texto_busqueda_usado": None,
                "total_resultados": len(resultados),
                "respuesta_ciudadana": {
                    "respuesta_corta": (
                        f"Para {departamento}, consulté la agrupación estadística de municipios "
                        "con comportamiento educativo similar. Esta lectura permite identificar "
                        "perfiles municipales comparables dentro del departamento."
                    ),
                    "hallazgos_principales": [
                        f"Se analizaron {resultado_analitico.get('total_municipios_analizados')} municipios.",
                        f"Se devuelven {len(resultados)} registros de municipios agrupados.",
                        "Los grupos estadísticos se construyen con indicadores educativos municipales estandarizados.",
                        "Esta agrupación es exploratoria y no representa un ranking de calidad educativa.",
                    ],
                    "fuente_usada": {
                        "dataset_key": "estadisticas_municipio",
                        "nombre": "MEN - Estadísticas en educación preescolar, básica y media por municipio",
                        "url": "https://www.datos.gov.co/resource/nudc-7mev.json",
                        "descripcion": "Indicadores municipales usados para comparar comportamientos educativos.",
                    },
                    "resultados_muestra": resultados,
                    "limitaciones": resultado_analitico.get("advertencias", []),
                    "sugerencias_de_siguiente_pregunta": [
                        "¿Qué grupo describe mejor a Villavicencio?",
                        "¿Qué recomendaciones educativas tiene Villavicencio?",
                        f"¿Qué relación hay entre bachilleres, educación superior e ICETEX en {departamento}?",
                    ],
                },
                "resultados": resultado_analitico,
                "nota_para_gpt": (
                    "Explica que, al no haber municipio base, se muestran grupos estadísticos "
                    "de municipios dentro del departamento. No lo presentes como ranking."
                ),
            }

        if not municipio:
            return respuesta_falta_territorio(
                pregunta=pregunta,
                intencion=clasificacion["intencion"],
                explicacion=clasificacion["explicacion"],
                dataset_usado="estadisticas_municipio",
                respuesta_corta=(
                    "Para comparar municipios o identificar su grupo educativo similar, "
                    "necesito que indiques un municipio."
                ),
                sugerencias=[
                    "¿Qué municipios se parecen a Villavicencio?",
                    "¿En qué grupo educativo está Soacha?",
                    "¿Qué recomendaciones educativas tiene Villavicencio?",
                ],
            )

        if not departamento:
            return {
                "pregunta_recibida": pregunta,
                "intencion_detectada": clasificacion["intencion"],
                "explicacion_enrutamiento": clasificacion["explicacion"],
                "dataset_usado": "estadisticas_municipio",
                "territorio_detectado": {
                    "departamento": departamento,
                    "municipio": municipio,
                },
                "texto_busqueda_usado": None,
                "total_resultados": 0,
                "respuesta_ciudadana": {
                    "respuesta_corta": (
                        "Identifiqué el municipio, pero necesito el departamento para evitar confusiones "
                        "con municipios que pueden tener nombres similares."
                    ),
                    "hallazgos_principales": [
                        f"Municipio detectado: {municipio}.",
                        "No se ejecutó la agrupación estadística porque falta el departamento.",
                    ],
                    "fuente_usada": {
                        "dataset_key": "estadisticas_municipio",
                        "nombre": "MEN - Estadísticas en educación preescolar, básica y media por municipio",
                        "url": "https://www.datos.gov.co/resource/nudc-7mev.json",
                        "descripcion": "Indicadores municipales usados para comparar comportamientos educativos.",
                    },
                    "resultados_muestra": [],
                    "limitaciones": [
                        "Para comparar municipios se requiere municipio y departamento.",
                    ],
                    "sugerencias_de_siguiente_pregunta": [
                        f"¿Qué municipios se parecen a {municipio}?",
                        f"¿Qué recomendaciones educativas tiene {municipio}?",
                    ],
                },
                "resultados": [],
                "nota_para_gpt": "Solicita departamento al usuario para ejecutar el análisis con precisión.",
            }

        if accion == "municipios_similares":
            resultado_analitico = buscar_municipios_similares_service(
                departamento=departamento,
                municipio=municipio,
                top_n=5,
                limit=limit_analitico,
            )

            similares = resultado_analitico.get("similares", [])

            return {
                "pregunta_recibida": pregunta,
                "intencion_detectada": "buscar_municipios_similares",
                "explicacion_enrutamiento": clasificacion["explicacion"],
                "dataset_usado": "estadisticas_municipio",
                "territorio_detectado": {
                    "departamento": departamento,
                    "municipio": municipio,
                },
                "texto_busqueda_usado": None,
                "total_resultados": len(similares),
                "respuesta_ciudadana": {
                    "respuesta_corta": (
                        f"Consulté el perfil educativo de {municipio}, {departamento}, "
                        "y busqué municipios con comportamiento educativo similar en los indicadores disponibles."
                    ),
                    "hallazgos_principales": [
                        f"Se encontraron {len(similares)} municipios similares.",
                        "La similitud se calcula con distancia estadística sobre variables educativas estandarizadas.",
                        "Una menor distancia indica mayor parecido en el conjunto de indicadores usados.",
                    ],
                    "fuente_usada": {
                        "dataset_key": "estadisticas_municipio",
                        "nombre": "MEN - Estadísticas en educación preescolar, básica y media por municipio",
                        "url": "https://www.datos.gov.co/resource/nudc-7mev.json",
                        "descripcion": "Indicadores municipales usados para comparar comportamientos educativos.",
                    },
                    "resultados_muestra": similares,
                    "limitaciones": resultado_analitico.get("advertencias", []),
                    "sugerencias_de_siguiente_pregunta": [
                        f"¿Qué recomendaciones educativas tiene {municipio}?",
                        f"¿En qué grupo educativo está {municipio}?",
                        "¿Qué variables se usaron para calcular la similitud?",
                    ],
                },
                "resultados": resultado_analitico,
                "nota_para_gpt": (
                    "Explica los municipios similares en lenguaje sencillo. "
                    "Aclara que menor distancia significa mayor similitud estadística, no igualdad territorial."
                ),
            }

        if accion == "recomendaciones_municipio":
            resultado_analitico = generar_recomendaciones_municipio_service(
                departamento=departamento,
                municipio=municipio,
                limit=limit_analitico,
            )

            return {
                "pregunta_recibida": pregunta,
                "intencion_detectada": "generar_recomendaciones_municipio",
                "explicacion_enrutamiento": clasificacion["explicacion"],
                "dataset_usado": "estadisticas_municipio",
                "territorio_detectado": {
                    "departamento": departamento,
                    "municipio": municipio,
                },
                "texto_busqueda_usado": None,
                "total_resultados": len(resultado_analitico.get("recomendaciones_generales", [])),
                "respuesta_ciudadana": {
                    "respuesta_corta": (
                        f"A partir del perfil educativo de {municipio}, {departamento}, "
                        "generé recomendaciones exploratorias basadas en su grupo de municipios similares."
                    ),
                    "hallazgos_principales": [
                        resultado_analitico.get("perfil_cluster")
                        or resultado_analitico.get("perfil_grupo_estadistico")
                        or "Se identificó un perfil educativo municipal.",
                        "Las recomendaciones son orientativas y deben contrastarse con información local.",
                    ],
                    "fuente_usada": {
                        "dataset_key": "estadisticas_municipio",
                        "nombre": "MEN - Estadísticas en educación preescolar, básica y media por municipio",
                        "url": "https://www.datos.gov.co/resource/nudc-7mev.json",
                        "descripcion": "Indicadores municipales usados para orientar recomendaciones exploratorias.",
                    },
                    "resultados_muestra": resultado_analitico.get("recomendaciones_generales", []),
                    "limitaciones": resultado_analitico.get("advertencias", []),
                    "sugerencias_de_siguiente_pregunta": [
                        f"¿Qué municipios se parecen a {municipio}?",
                        "¿Cómo se puede cruzar este resultado con colegios, bachilleres o educación superior?",
                    ],
                },
                "resultados": resultado_analitico,
                "nota_para_gpt": (
                    "Presenta las recomendaciones como orientaciones exploratorias, no como diagnóstico definitivo."
                ),
            }

        if accion == "perfil_cluster_municipio":
            resultado_analitico = consultar_cluster_municipio_service(
                departamento=departamento,
                municipio=municipio,
                limit=limit_analitico,
            )

            grupo = (
                resultado_analitico.get("grupo_estadistico_asignado")
                or resultado_analitico.get("cluster_asignado")
            )

            return {
                "pregunta_recibida": pregunta,
                "intencion_detectada": "consultar_grupo_educativo_municipio",
                "explicacion_enrutamiento": clasificacion["explicacion"],
                "dataset_usado": "estadisticas_municipio",
                "territorio_detectado": {
                    "departamento": departamento,
                    "municipio": municipio,
                },
                "texto_busqueda_usado": None,
                "total_resultados": 1,
                "respuesta_ciudadana": {
                    "respuesta_corta": (
                        f"{municipio}, {departamento}, pertenece al grupo estadístico {grupo} "
                        "de municipios con comportamiento educativo similar, según los indicadores disponibles."
                    ),
                    "hallazgos_principales": [
                        resultado_analitico.get("explicacion_grupo_estadistico")
                        or resultado_analitico.get("explicacion_cluster")
                        or "Se identificó un perfil educativo municipal.",
                        "Esta agrupación es exploratoria y no representa un ranking de calidad.",
                        "El análisis compara patrones educativos entre municipios usando variables estandarizadas.",
                    ],
                    "fuente_usada": {
                        "dataset_key": "estadisticas_municipio",
                        "nombre": "MEN - Estadísticas en educación preescolar, básica y media por municipio",
                        "url": "https://www.datos.gov.co/resource/nudc-7mev.json",
                        "descripcion": "Indicadores municipales usados para agrupar municipios con comportamiento educativo similar.",
                    },
                    "resultados_muestra": [
                        {
                            "municipio": resultado_analitico.get("municipio_consultado"),
                            "departamento": resultado_analitico.get("departamento"),
                            "grupo_estadistico": grupo,
                            "explicacion": (
                                resultado_analitico.get("explicacion_grupo_estadistico")
                                or resultado_analitico.get("explicacion_cluster")
                            ),
                            "variables": resultado_analitico.get("variables_mas_relevantes", {}).get(
                                "variables_legibles",
                                resultado_analitico.get("variables_mas_relevantes", {}).get(
                                    "variables_usadas",
                                    []
                                )
                            ),
                        }
                    ],
                    "limitaciones": resultado_analitico.get("advertencias_o_limitaciones", []),
                    "sugerencias_de_siguiente_pregunta": [
                        f"¿Qué municipios se parecen a {municipio}?",
                        f"¿Qué recomendaciones educativas tiene {municipio}?",
                        "¿Qué significan las variables altas y bajas de este grupo?",
                    ],
                },
                "resultados": resultado_analitico,
                "nota_para_gpt": (
                    "Explica la agrupación como comparación estadística exploratoria, no como ranking."
                ),
            }

    # --------------------------------------------------------
    # Establecimientos educativos
    # --------------------------------------------------------
    if clasificacion.get("intencion") == "buscar_establecimientos_educativos":
        if not departamento and not municipio:
            return respuesta_falta_territorio(
                pregunta=pregunta,
                intencion=clasificacion["intencion"],
                explicacion=clasificacion["explicacion"],
                dataset_usado=clasificacion["dataset_key"],
                respuesta_corta=(
                    "Puedo ayudarte a consultar colegios o establecimientos educativos, "
                    "pero necesito identificar al menos un municipio o departamento."
                ),
                sugerencias=[
                    "¿Cuántos colegios hay en Soacha?",
                    "¿Cuántos colegios oficiales y privados hay en Villavicencio?",
                    "Muéstrame la lista de colegios oficiales de Villavicencio",
                ],
            )

        sector_detectado = detectar_sector_establecimiento(pregunta)
        modo_respuesta = detectar_modo_respuesta_establecimientos(pregunta)

        resultado_establecimientos = consultar_establecimientos_educativos_service(
            departamento=departamento,
            municipio=municipio,
            sector=sector_detectado,
            limit=limit_analitico,
            modo_respuesta=modo_respuesta,
        )

        datos_establecimientos = resultado_establecimientos.get("datos", {})

        if modo_respuesta == "lista":
            resultados_muestra = datos_establecimientos.get("lista_establecimientos", [])
        else:
            resultados_muestra = []

        return {
            "pregunta_recibida": pregunta,
            "intencion_detectada": clasificacion["intencion"],
            "modo_respuesta": modo_respuesta,
            "explicacion_enrutamiento": clasificacion["explicacion"],
            "dataset_usado": clasificacion["dataset_key"],
            "territorio_detectado": {
                "departamento": departamento,
                "municipio": municipio,
                "sector": sector_detectado,
            },
            "texto_busqueda_usado": None,
            "total_resultados": datos_establecimientos.get("total_establecimientos_unicos"),
            "respuesta_ciudadana": {
                "respuesta_corta": resultado_establecimientos["respuesta_corta"],
                "hallazgos_principales": resultado_establecimientos["hallazgos_principales"],
                "fuente_usada": resultado_establecimientos["fuentes_usadas"][0],
                "resultados_muestra": resultados_muestra,
                "limitaciones": resultado_establecimientos["limitaciones"],
                "sugerencias_de_siguiente_pregunta": resultado_establecimientos[
                    "sugerencias_de_siguiente_pregunta"
                ],
                "modo_respuesta": modo_respuesta,
            },
            "resultados": resultado_establecimientos,
            "nota_para_gpt": (
                "Si modo_respuesta es conteo, presenta solo el resumen numérico y pregunta "
                "si desea ver la lista de colegios oficiales o no oficiales. "
                "Si modo_respuesta es lista, presenta la lista filtrada por la vigencia más reciente."
            ),
        }

    # --------------------------------------------------------
    # Programas de educación superior
    # --------------------------------------------------------
    if clasificacion.get("intencion") == "buscar_programas_educacion_superior":
        texto_busqueda = detectar_texto_especifico(
            pregunta=pregunta,
            municipio=municipio,
            departamento=departamento,
        )

        if es_texto_generico_educativo(texto_busqueda):
            texto_busqueda = None

        if not departamento and not municipio and not texto_busqueda:
            return respuesta_falta_territorio(
                pregunta=pregunta,
                intencion=clasificacion["intencion"],
                explicacion=clasificacion["explicacion"],
                dataset_usado=clasificacion["dataset_key"],
                respuesta_corta=(
                    "Puedo ayudarte a consultar programas de educación superior, "
                    "pero necesito identificar un municipio, departamento, institución o programa."
                ),
                sugerencias=[
                    "¿Qué programas de educación superior hay en Medellín?",
                    "¿Qué universidades ofrecen programas en Cali?",
                    "¿Qué programas de ingeniería hay en Bogotá?",
                ],
            )

        resultado_programas = consultar_programas_superior_service(
            departamento=departamento,
            municipio=municipio,
            texto=texto_busqueda,
            limit=limit_analitico,
        )

        return {
            "pregunta_recibida": pregunta,
            "intencion_detectada": clasificacion["intencion"],
            "explicacion_enrutamiento": clasificacion["explicacion"],
            "dataset_usado": clasificacion["dataset_key"],
            "territorio_detectado": {
                "departamento": departamento,
                "municipio": municipio,
            },
            "texto_busqueda_usado": texto_busqueda,
            "total_resultados": resultado_programas["datos"].get("total_programas_unicos"),
            "respuesta_ciudadana": {
                "respuesta_corta": resultado_programas["respuesta_corta"],
                "hallazgos_principales": resultado_programas["hallazgos_principales"],
                "fuente_usada": resultado_programas["fuentes_usadas"][0],
                "resultados_muestra": resultado_programas["datos"].get("muestra_programas", []),
                "limitaciones": resultado_programas["limitaciones"],
                "sugerencias_de_siguiente_pregunta": resultado_programas[
                    "sugerencias_de_siguiente_pregunta"
                ],
            },
            "resultados": resultado_programas,
            "nota_para_gpt": (
                "Presenta programas únicos, instituciones y modalidad. "
                "Aclara que un mismo programa puede repetirse por sede, municipio o modalidad."
            ),
        }

    # --------------------------------------------------------
    # Bachilleres
    # --------------------------------------------------------
    if clasificacion.get("intencion") == "consultar_bachilleres":
        if not departamento and not municipio:
            return respuesta_falta_territorio(
                pregunta=pregunta,
                intencion=clasificacion["intencion"],
                explicacion=clasificacion["explicacion"],
                dataset_usado=clasificacion["dataset_key"],
                respuesta_corta=(
                    "Puedo ayudarte a consultar bachilleres o egresados de educación media, "
                    "pero necesito identificar al menos un municipio o departamento."
                ),
                sugerencias=[
                    "¿Cuántos bachilleres hay en Meta?",
                    "¿Cuántos bachilleres se graduaron en Villavicencio?",
                    "¿Cómo se relacionan bachilleres, educación superior e ICETEX en Meta?",
                ],
            )

        resultado_bachilleres = consultar_bachilleres_service(
            departamento=departamento,
            municipio=municipio,
            limit=limit_analitico,
        )

        return {
            "pregunta_recibida": pregunta,
            "intencion_detectada": clasificacion["intencion"],
            "explicacion_enrutamiento": clasificacion["explicacion"],
            "dataset_usado": clasificacion["dataset_key"],
            "territorio_detectado": {
                "departamento": departamento,
                "municipio": municipio,
            },
            "texto_busqueda_usado": None,
            "total_resultados": resultado_bachilleres["datos"].get("total_bachilleres_aproximado"),
            "respuesta_ciudadana": {
                "respuesta_corta": resultado_bachilleres["respuesta_corta"],
                "hallazgos_principales": resultado_bachilleres["hallazgos_principales"],
                "fuente_usada": resultado_bachilleres["fuentes_usadas"][0],
                "resultados_muestra": resultado_bachilleres["datos"].get("muestra_bachilleres", []),
                "limitaciones": resultado_bachilleres["limitaciones"],
                "sugerencias_de_siguiente_pregunta": resultado_bachilleres[
                    "sugerencias_de_siguiente_pregunta"
                ],
            },
            "resultados": resultado_bachilleres,
            "nota_para_gpt": (
                "Presenta el dato como aproximación descriptiva. "
                "Aclara que depende de la columna detectada y de la vigencia disponible."
            ),
        }

    # --------------------------------------------------------
    # ICETEX
    # --------------------------------------------------------
    if clasificacion.get("intencion") in [
        "consultar_creditos_icetex_otorgados",
        "consultar_creditos_icetex_renovados",
    ]:
        if not departamento and not municipio:
            return respuesta_falta_territorio(
                pregunta=pregunta,
                intencion=clasificacion["intencion"],
                explicacion=clasificacion["explicacion"],
                dataset_usado=clasificacion["dataset_key"],
                respuesta_corta=(
                    "Puedo ayudarte a consultar créditos ICETEX, pero necesito identificar "
                    "al menos un municipio o departamento."
                ),
                sugerencias=[
                    "¿Qué créditos ICETEX hay en Meta?",
                    "¿Qué créditos ICETEX renovados aparecen en Cundinamarca?",
                    "¿Cómo se relacionan bachilleres, educación superior e ICETEX en Meta?",
                ],
            )

        tipo_icetex = (
            "renovados"
            if clasificacion.get("intencion") == "consultar_creditos_icetex_renovados"
            else "otorgados"
        )

        resultado_icetex = consultar_icetex_service(
            departamento=departamento,
            municipio=municipio,
            tipo=tipo_icetex,
            limit=limit_analitico,
        )

        total_resultados = (
            resultado_icetex["datos"].get("total_creditos_o_beneficiarios_aproximado")
            or resultado_icetex["datos"].get("total_registros_vigencia")
            or 0
        )

        return {
            "pregunta_recibida": pregunta,
            "intencion_detectada": clasificacion["intencion"],
            "explicacion_enrutamiento": clasificacion["explicacion"],
            "dataset_usado": clasificacion["dataset_key"],
            "territorio_detectado": {
                "departamento": departamento,
                "municipio": municipio,
                "tipo_icetex": tipo_icetex,
            },
            "texto_busqueda_usado": None,
            "total_resultados": total_resultados,
            "respuesta_ciudadana": {
                "respuesta_corta": resultado_icetex["respuesta_corta"],
                "hallazgos_principales": resultado_icetex["hallazgos_principales"],
                "fuente_usada": resultado_icetex["fuentes_usadas"][0],
                "resultados_muestra": resultado_icetex["datos"].get("muestra_icetex", []),
                "limitaciones": resultado_icetex["limitaciones"],
                "sugerencias_de_siguiente_pregunta": resultado_icetex[
                    "sugerencias_de_siguiente_pregunta"
                ],
            },
            "resultados": resultado_icetex,
            "nota_para_gpt": (
                "Presenta el dato como aproximación descriptiva. "
                "Si no hay columna numérica confiable, reporta registros disponibles."
            ),
        }

    # --------------------------------------------------------
    # Ruta genérica por dataset
    # --------------------------------------------------------
    texto_busqueda = detectar_texto_especifico(
        pregunta=pregunta,
        municipio=municipio,
        departamento=departamento,
    )

    if es_texto_generico_educativo(texto_busqueda):
        texto_busqueda = None

    resultado = buscar_en_dataset(
        dataset_key=clasificacion["dataset_key"],
        texto=texto_busqueda,
        departamento=departamento,
        municipio=municipio,
        limit=limit_analitico,
    )

    respuesta_ciudadana = construir_respuesta_ciudadana(
        pregunta=pregunta,
        intencion=clasificacion["intencion"],
        dataset_key=clasificacion["dataset_key"],
        dataset=resultado["dataset"],
        total_resultados=resultado["total_resultados"],
        resultados=resultado["resultados"],
    )

    return {
        "pregunta_recibida": pregunta,
        "intencion_detectada": clasificacion["intencion"],
        "explicacion_enrutamiento": clasificacion["explicacion"],
        "dataset_usado": clasificacion["dataset_key"],
        "territorio_detectado": {
            "departamento": departamento,
            "municipio": municipio,
        },
        "texto_busqueda_usado": texto_busqueda,
        "total_resultados": resultado["total_resultados"],
        "respuesta_ciudadana": respuesta_ciudadana,
        "resultados": resultado["resultados"],
        "nota_para_gpt": (
            "Prioriza la respuesta_ciudadana para responder al usuario. "
            "Usa resultados solo como evidencia adicional. "
            "No afirmes causalidad ni conclusiones no soportadas por los datos."
        ),
    }
