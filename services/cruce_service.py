from typing import Any, Dict, Optional

from services.bachilleres_service import consultar_bachilleres_service
from services.programas_service import consultar_programas_superior_service
from services.icetex_service import consultar_icetex_service

try:
    from config import (
        MAX_LIMIT,
        DEFAULT_ANALYTIC_LIMIT,
        MIN_LIMIT_MUNICIPAL,
        MIN_LIMIT_DEPARTAMENTAL,
    )
except Exception:
    MAX_LIMIT = 1_000_000
    DEFAULT_ANALYTIC_LIMIT = 100_000
    MIN_LIMIT_MUNICIPAL = 100_000
    MIN_LIMIT_DEPARTAMENTAL = 500_000


# ============================================================
# Utilidades generales
# ============================================================

def resolver_limit_cruce(
    departamento: Optional[str],
    municipio: Optional[str],
    limit: Optional[int]
) -> int:
    """
    Define un límite amplio para el cruce de tránsito educativo.

    El cruce necesita suficiente volumen porque consulta varias fuentes:
    - bachilleres,
    - programas de educación superior,
    - ICETEX otorgados,
    - ICETEX renovados.
    """
    try:
        limit_solicitado = int(limit) if limit is not None else DEFAULT_ANALYTIC_LIMIT
    except (TypeError, ValueError):
        limit_solicitado = DEFAULT_ANALYTIC_LIMIT

    if departamento and not municipio:
        limit_final = max(limit_solicitado, MIN_LIMIT_DEPARTAMENTAL)
    elif municipio:
        limit_final = max(limit_solicitado, MIN_LIMIT_MUNICIPAL)
    else:
        limit_final = max(limit_solicitado, DEFAULT_ANALYTIC_LIMIT)

    return min(limit_final, MAX_LIMIT)


def ejecutar_seguro(nombre: str, funcion, *args, **kwargs) -> Dict[str, Any]:
    """
    Ejecuta un servicio y evita que un error parcial dañe todo el cruce.
    """
    try:
        return {
            "ok": True,
            "nombre": nombre,
            "datos": funcion(*args, **kwargs),
            "error": None
        }
    except Exception as error:
        return {
            "ok": False,
            "nombre": nombre,
            "datos": None,
            "error": str(error)
        }


def extraer_datos_servicio(resultado: Dict[str, Any]) -> Dict[str, Any]:
    if not resultado.get("ok") or not resultado.get("datos"):
        return {}

    return resultado["datos"].get("datos", {}) or {}


def extraer_respuesta_servicio(resultado: Dict[str, Any]) -> str:
    if not resultado.get("ok") or not resultado.get("datos"):
        return ""

    return resultado["datos"].get("respuesta_corta", "") or ""


def extraer_hallazgos_servicio(resultado: Dict[str, Any]) -> list:
    if not resultado.get("ok") or not resultado.get("datos"):
        return []

    return resultado["datos"].get("hallazgos_principales", []) or []


def formato_numero(valor: Any) -> str:
    """
    Formatea números para respuesta ciudadana.
    """
    if valor is None:
        return "sin dato consolidado"

    try:
        return f"{int(round(float(valor))):,}"
    except (TypeError, ValueError):
        return str(valor)


# ============================================================
# Resúmenes por fuente
# ============================================================

def resumir_bachilleres(resultado: Dict[str, Any]) -> Dict[str, Any]:
    datos = extraer_datos_servicio(resultado)

    return {
        "ok": resultado.get("ok"),
        "error": resultado.get("error"),
        "respuesta_corta": extraer_respuesta_servicio(resultado),
        "anio_usado": datos.get("anio_usado"),
        "limit_usado": datos.get("limit_usado"),
        "q_inicial": datos.get("q_inicial"),
        "total_registros_descargados": datos.get("total_registros_descargados"),
        "total_registros_historicos": datos.get("total_registros_historicos"),
        "total_registros_vigencia": datos.get("total_registros_vigencia"),
        "total_bachilleres_aproximado": datos.get("total_bachilleres_aproximado"),
        "distribucion_secretaria_o_etc": datos.get("distribucion_secretaria_o_etc", []),
        "columna_bachilleres": datos.get("columnas_detectadas", {}).get("bachilleres"),
        "muestra": datos.get("muestra_bachilleres", [])
    }


def resumir_programas(resultado: Dict[str, Any]) -> Dict[str, Any]:
    datos = extraer_datos_servicio(resultado)

    return {
        "ok": resultado.get("ok"),
        "error": resultado.get("error"),
        "respuesta_corta": extraer_respuesta_servicio(resultado),
        "limit_usado": datos.get("limit_usado"),
        "q_inicial": datos.get("q_inicial"),
        "total_registros_descargados": datos.get("total_registros_descargados"),
        "total_registros": datos.get("total_registros"),
        "total_programas_unicos": datos.get("total_programas_unicos"),
        "total_programas_activos_unicos": datos.get("total_programas_activos_unicos"),
        "total_instituciones_unicas": datos.get("total_instituciones_unicas"),
        "distribucion_nivel": datos.get("distribucion_nivel", []),
        "distribucion_metodologia": datos.get("distribucion_metodologia", []),
        "distribucion_area": datos.get("distribucion_area", []),
        "distribucion_estado": datos.get("distribucion_estado", []),
        "instituciones_frecuentes": datos.get("instituciones_frecuentes", []),
        "programas_frecuentes": datos.get("programas_frecuentes", []),
        "muestra": datos.get("muestra_programas", [])
    }


def resumir_icetex(resultado: Dict[str, Any]) -> Dict[str, Any]:
    datos = extraer_datos_servicio(resultado)

    return {
        "ok": resultado.get("ok"),
        "error": resultado.get("error"),
        "respuesta_corta": extraer_respuesta_servicio(resultado),
        "anio_usado": datos.get("anio_usado"),
        "limit_usado": datos.get("limit_usado"),
        "q_inicial": datos.get("q_inicial"),
        "tipo_credito": datos.get("tipo_credito"),
        "total_registros_descargados": datos.get("total_registros_descargados"),
        "total_registros_historicos": datos.get("total_registros_historicos"),
        "total_registros_vigencia": datos.get("total_registros_vigencia"),
        "total_creditos_o_beneficiarios_aproximado": datos.get(
            "total_creditos_o_beneficiarios_aproximado"
        ),
        "lineas_o_modalidades_frecuentes": datos.get("lineas_o_modalidades_frecuentes", []),
        "instituciones_frecuentes": datos.get("instituciones_frecuentes", []),
        "sectores_frecuentes": datos.get("sectores_frecuentes", []),
        "muestra": datos.get("muestra_icetex", [])
    }


# ============================================================
# Lectura integrada
# ============================================================

def construir_lectura_integrada(
    departamento: Optional[str],
    municipio: Optional[str],
    resumen_bachilleres: Dict[str, Any],
    resumen_programas: Dict[str, Any],
    resumen_icetex_otorgados: Dict[str, Any],
    resumen_icetex_renovados: Dict[str, Any]
) -> list:
    """
    Construye lectura ciudadana integrada del tránsito educativo.
    """
    territorio = municipio or departamento or "el territorio consultado"

    hallazgos = []

    total_bachilleres = resumen_bachilleres.get("total_bachilleres_aproximado")
    total_programas = resumen_programas.get("total_programas_unicos")
    total_programas_activos = resumen_programas.get("total_programas_activos_unicos")
    total_instituciones = resumen_programas.get("total_instituciones_unicas")
    total_otorgados = resumen_icetex_otorgados.get("total_creditos_o_beneficiarios_aproximado")
    total_renovados = resumen_icetex_renovados.get("total_creditos_o_beneficiarios_aproximado")

    if resumen_bachilleres.get("ok"):
        if total_bachilleres is not None:
            hallazgos.append(
                f"En {territorio}, se estimaron aproximadamente "
                f"{formato_numero(total_bachilleres)} bachilleres o egresados de educación media "
                "en la vigencia más reciente detectada."
            )
        else:
            hallazgos.append(
                f"En {territorio}, se encontraron registros de bachilleres, "
                "pero no fue posible consolidar una suma numérica confiable."
            )
    else:
        hallazgos.append(
            f"No fue posible consolidar bachilleres para {territorio}: "
            f"{resumen_bachilleres.get('error')}"
        )

    if resumen_programas.get("ok"):
        hallazgos.append(
            f"En oferta de educación superior, se estimaron "
            f"{formato_numero(total_programas or 0)} programas únicos en "
            f"{formato_numero(total_instituciones or 0)} instituciones."
        )

        if total_programas_activos is not None:
            hallazgos.append(
                f"De esos programas, aproximadamente {formato_numero(total_programas_activos)} "
                "aparecen como activos según la columna de estado detectada."
            )

        metodologias = resumen_programas.get("distribucion_metodologia", [])
        if metodologias:
            principales = ", ".join(
                f"{item.get('valor')}: {item.get('conteo')}"
                for item in metodologias[:3]
            )
            hallazgos.append(
                f"Las metodologías o modalidades más frecuentes en la oferta detectada son: {principales}."
            )

        niveles = resumen_programas.get("distribucion_nivel", [])
        if niveles:
            principales_niveles = ", ".join(
                f"{item.get('valor')}: {item.get('conteo')}"
                for item in niveles[:3]
            )
            hallazgos.append(
                f"Los niveles académicos más frecuentes en la oferta detectada son: {principales_niveles}."
            )
    else:
        hallazgos.append(
            f"No fue posible consolidar la oferta de educación superior para {territorio}: "
            f"{resumen_programas.get('error')}"
        )

    if resumen_icetex_otorgados.get("ok"):
        if total_otorgados is not None:
            hallazgos.append(
                "En créditos ICETEX otorgados, se estimó una suma aproximada de "
                f"{formato_numero(total_otorgados)} créditos o beneficiarios en la vigencia más reciente detectada."
            )
        else:
            hallazgos.append(
                "Se encontraron registros de créditos ICETEX otorgados, "
                "pero no fue posible consolidar una suma numérica confiable."
            )
    else:
        hallazgos.append(
            f"No fue posible consolidar créditos ICETEX otorgados para {territorio}: "
            f"{resumen_icetex_otorgados.get('error')}"
        )

    if resumen_icetex_renovados.get("ok"):
        if total_renovados is not None:
            hallazgos.append(
                "En créditos ICETEX renovados, se estimó una suma aproximada de "
                f"{formato_numero(total_renovados)} renovaciones, créditos o beneficiarios "
                "en la vigencia más reciente detectada."
            )
        else:
            hallazgos.append(
                "Se encontraron registros de créditos ICETEX renovados, "
                "pero no fue posible consolidar una suma numérica confiable."
            )
    else:
        hallazgos.append(
            f"No fue posible consolidar créditos ICETEX renovados para {territorio}: "
            f"{resumen_icetex_renovados.get('error')}"
        )

    if (
        total_bachilleres is not None
        and total_programas is not None
        and total_programas > 0
    ):
        hallazgos.append(
            "La presencia simultánea de bachilleres y oferta de educación superior "
            "permite formular preguntas sobre tránsito educativo, acceso territorial "
            "y continuidad formativa."
        )

    if (
        total_bachilleres is not None
        and (
            total_otorgados is not None
            or total_renovados is not None
        )
    ):
        hallazgos.append(
            "La información de ICETEX permite explorar apoyos financieros asociados "
            "al acceso o permanencia en educación superior, pero no prueba por sí sola "
            "que los bachilleres accedan efectivamente a esos créditos."
        )

    if (
        total_programas is not None
        and total_programas > 0
        and total_otorgados is None
        and total_renovados is None
    ):
        hallazgos.append(
            "Aunque se detecta oferta de educación superior, los registros ICETEX disponibles "
            "no permiten consolidar una suma numérica de apoyos financieros para el mismo territorio."
        )

    hallazgos.append(
        "Esta lectura conecta dimensiones del tránsito educativo, pero debe entenderse "
        "como análisis descriptivo y exploratorio, no como relación causal."
    )

    return hallazgos


def construir_alertas_integradas(
    resumen_bachilleres: Dict[str, Any],
    resumen_programas: Dict[str, Any],
    resumen_icetex_otorgados: Dict[str, Any],
    resumen_icetex_renovados: Dict[str, Any]
) -> list:
    """
    Genera alertas ciudadanas simples a partir de ausencia o baja disponibilidad de datos.
    """
    alertas = []

    if not resumen_bachilleres.get("ok"):
        alertas.append("No se pudo consolidar la dimensión de bachilleres.")

    if not resumen_programas.get("ok"):
        alertas.append("No se pudo consolidar la dimensión de oferta de educación superior.")

    if not resumen_icetex_otorgados.get("ok"):
        alertas.append("No se pudo consolidar la dimensión de créditos ICETEX otorgados.")

    if not resumen_icetex_renovados.get("ok"):
        alertas.append("No se pudo consolidar la dimensión de créditos ICETEX renovados.")

    total_programas = resumen_programas.get("total_programas_unicos")
    if total_programas == 0:
        alertas.append(
            "No se detectó oferta de programas de educación superior con los filtros usados."
        )

    total_bachilleres = resumen_bachilleres.get("total_bachilleres_aproximado")
    if total_bachilleres is None:
        alertas.append(
            "No se logró estimar una suma consolidada de bachilleres con las columnas detectadas."
        )

    total_otorgados = resumen_icetex_otorgados.get("total_creditos_o_beneficiarios_aproximado")
    total_renovados = resumen_icetex_renovados.get("total_creditos_o_beneficiarios_aproximado")

    if total_otorgados is None and total_renovados is None:
        alertas.append(
            "No se logró estimar una suma consolidada de créditos ICETEX otorgados o renovados."
        )

    if not alertas:
        alertas.append(
            "Las cuatro dimensiones principales se procesaron correctamente, con las limitaciones propias de datos abiertos."
        )

    return alertas


def construir_resumen_ejecutivo(
    territorio: str,
    resumen_bachilleres: Dict[str, Any],
    resumen_programas: Dict[str, Any],
    resumen_icetex_otorgados: Dict[str, Any],
    resumen_icetex_renovados: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Construye un resumen sintético para que la app o el GPT puedan mostrar
    datos relevantes sin navegar todo el JSON.
    """
    return {
        "territorio": territorio,
        "bachilleres_aproximados": resumen_bachilleres.get("total_bachilleres_aproximado"),
        "anio_bachilleres": resumen_bachilleres.get("anio_usado"),
        "programas_superior_unicos": resumen_programas.get("total_programas_unicos"),
        "programas_superior_activos_unicos": resumen_programas.get("total_programas_activos_unicos"),
        "instituciones_superior_unicas": resumen_programas.get("total_instituciones_unicas"),
        "icetex_otorgados_aproximados": resumen_icetex_otorgados.get(
            "total_creditos_o_beneficiarios_aproximado"
        ),
        "anio_icetex_otorgados": resumen_icetex_otorgados.get("anio_usado"),
        "icetex_renovados_aproximados": resumen_icetex_renovados.get(
            "total_creditos_o_beneficiarios_aproximado"
        ),
        "anio_icetex_renovados": resumen_icetex_renovados.get("anio_usado")
    }


# ============================================================
# Servicio principal
# ============================================================

def analizar_transito_educativo_service(
    departamento: Optional[str] = None,
    municipio: Optional[str] = None,
    limit: int = DEFAULT_ANALYTIC_LIMIT
) -> Dict[str, Any]:
    """
    Cruce exploratorio entre:
    - bachilleres,
    - oferta de educación superior,
    - créditos ICETEX otorgados,
    - créditos ICETEX renovados.

    Mantiene la misma firma usada por consulta_service.py.
    """

    if not departamento and not municipio:
        raise ValueError(
            "Debes indicar al menos un departamento o municipio para analizar el tránsito educativo."
        )

    limit_final = resolver_limit_cruce(
        departamento=departamento,
        municipio=municipio,
        limit=limit
    )

    territorio = municipio or departamento

    bachilleres = ejecutar_seguro(
        "bachilleres",
        consultar_bachilleres_service,
        departamento=departamento,
        municipio=municipio,
        limit=limit_final
    )

    programas = ejecutar_seguro(
        "programas_superior",
        consultar_programas_superior_service,
        departamento=departamento,
        municipio=municipio,
        texto=None,
        limit=limit_final
    )

    icetex_otorgados = ejecutar_seguro(
        "icetex_otorgados",
        consultar_icetex_service,
        departamento=departamento,
        municipio=municipio,
        tipo="otorgados",
        limit=limit_final
    )

    icetex_renovados = ejecutar_seguro(
        "icetex_renovados",
        consultar_icetex_service,
        departamento=departamento,
        municipio=municipio,
        tipo="renovados",
        limit=limit_final
    )

    resumen_bachilleres = resumir_bachilleres(bachilleres)
    resumen_programas = resumir_programas(programas)
    resumen_icetex_otorgados = resumir_icetex(icetex_otorgados)
    resumen_icetex_renovados = resumir_icetex(icetex_renovados)

    hallazgos = construir_lectura_integrada(
        departamento=departamento,
        municipio=municipio,
        resumen_bachilleres=resumen_bachilleres,
        resumen_programas=resumen_programas,
        resumen_icetex_otorgados=resumen_icetex_otorgados,
        resumen_icetex_renovados=resumen_icetex_renovados
    )

    alertas = construir_alertas_integradas(
        resumen_bachilleres=resumen_bachilleres,
        resumen_programas=resumen_programas,
        resumen_icetex_otorgados=resumen_icetex_otorgados,
        resumen_icetex_renovados=resumen_icetex_renovados
    )

    resumen_ejecutivo = construir_resumen_ejecutivo(
        territorio=territorio,
        resumen_bachilleres=resumen_bachilleres,
        resumen_programas=resumen_programas,
        resumen_icetex_otorgados=resumen_icetex_otorgados,
        resumen_icetex_renovados=resumen_icetex_renovados
    )

    return {
        "tipo_analisis": "cruce_transito_educativo",
        "territorio_consultado": {
            "departamento": departamento,
            "municipio": municipio
        },
        "limites_usados": {
            "limit_solicitado": limit,
            "limit_final": limit_final
        },
        "respuesta_corta": (
            f"Se realizó un cruce exploratorio para {territorio}, integrando bachilleres, "
            "oferta de educación superior y créditos ICETEX otorgados y renovados. "
            "El análisis permite orientar preguntas sobre tránsito educativo, acceso, "
            "financiación y continuidad formativa, sin afirmar causalidad."
        ),
        "hallazgos_principales": hallazgos,
        "alertas_de_lectura": alertas,
        "resumen_ejecutivo": resumen_ejecutivo,
        "resumen_por_fuente": {
            "bachilleres": resumen_bachilleres,
            "programas_superior": resumen_programas,
            "icetex_otorgados": resumen_icetex_otorgados,
            "icetex_renovados": resumen_icetex_renovados
        },
        "componentes_crudos": {
            "bachilleres": bachilleres,
            "programas_superior": programas,
            "icetex_otorgados": icetex_otorgados,
            "icetex_renovados": icetex_renovados
        },
        "fuentes_usadas": [
            {
                "dataset_key": "bachilleres",
                "nombre": "Número de bachilleres por entidad territorial certificada",
                "url": "https://www.datos.gov.co/resource/5c2k-ahfc.json"
            },
            {
                "dataset_key": "programas_superior",
                "nombre": "Programas de educación superior",
                "url": "https://www.datos.gov.co/resource/upr9-nkiz.json"
            },
            {
                "dataset_key": "icetex_otorgados",
                "nombre": "Créditos otorgados por ICETEX",
                "url": "https://www.datos.gov.co/resource/26bn-e42j.json"
            },
            {
                "dataset_key": "icetex_renovados",
                "nombre": "Créditos renovados por ICETEX",
                "url": "https://www.datos.gov.co/resource/nvcf-b8a3.json"
            }
        ],
        "limitaciones": [
            "El cruce es exploratorio y depende de la disponibilidad, actualización y estructura de cada dataset.",
            "Las columnas pueden variar entre fuentes; por eso la API detecta campos relevantes de forma flexible.",
            "Los resultados no prueban causalidad entre bachilleres, oferta educativa y financiación.",
            "Los conteos son aproximados cuando dependen de columnas detectadas automáticamente.",
            "Las vigencias pueden no coincidir entre bachilleres, educación superior e ICETEX.",
            "Para decisiones públicas se recomienda contrastar estos hallazgos con información institucional y territorial."
        ],
        "sugerencias_de_siguiente_pregunta": [
            f"¿Qué programas de educación superior aparecen en {territorio}?",
            f"¿Qué créditos ICETEX otorgados aparecen en {territorio}?",
            f"¿Qué créditos ICETEX renovados aparecen en {territorio}?",
            f"¿Qué recomendaciones educativas surgen para mejorar el tránsito hacia educación superior en {territorio}?"
        ]
    }