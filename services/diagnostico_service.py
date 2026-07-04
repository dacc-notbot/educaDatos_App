from typing import Any, Dict, Optional

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

from services.clustering_service import (
    consultar_cluster_municipio_service,
    buscar_municipios_similares_service,
    generar_recomendaciones_municipio_service,
)

from services.establecimientos_service import consultar_establecimientos_educativos_service
from services.programas_service import consultar_programas_superior_service
from services.cruce_service import analizar_transito_educativo_service


# ============================================================
# Límites para diagnóstico
# ============================================================

def resolver_limites_diagnostico(
    departamento: Optional[str],
    municipio: Optional[str],
    limit: Optional[int]
) -> Dict[str, Any]:
    """
    Define límites amplios para diagnóstico territorial.

    Reglas:
    - Municipio: mínimo 100.000 registros.
    - Departamento: mínimo 500.000 registros.
    - Nunca supera MAX_LIMIT.
    """
    try:
        limit_solicitado = int(limit) if limit is not None else DEFAULT_ANALYTIC_LIMIT
    except (TypeError, ValueError):
        limit_solicitado = DEFAULT_ANALYTIC_LIMIT

    if municipio:
        escala = "municipal"
        minimo = MIN_LIMIT_MUNICIPAL
    else:
        escala = "departamental"
        minimo = MIN_LIMIT_DEPARTAMENTAL

    limit_final = min(
        max(limit_solicitado, minimo),
        MAX_LIMIT
    )

    return {
        "escala": escala,
        "limit_solicitado": limit_solicitado,
        "limit_minimo_aplicado": minimo,
        "limit_maximo_permitido": MAX_LIMIT,
        "limit_final": limit_final,
        "limit_agrupacion_estadistica": limit_final,
        "limit_descriptivo": limit_final,
        "limit_transito": limit_final,
    }


# ============================================================
# Utilidades generales
# ============================================================

def ejecutar_seguro(nombre: str, funcion, *args, **kwargs) -> Dict[str, Any]:
    """
    Ejecuta una función y evita que un error parcial dañe todo el diagnóstico.
    """
    try:
        return {
            "ok": True,
            "nombre": nombre,
            "datos": funcion(*args, **kwargs),
            "error": None,
        }
    except Exception as error:
        return {
            "ok": False,
            "nombre": nombre,
            "datos": None,
            "error": str(error),
        }


def extraer_datos(resultado: Dict[str, Any]) -> Dict[str, Any]:
    if not resultado.get("ok") or not resultado.get("datos"):
        return {}

    datos = resultado["datos"]

    if isinstance(datos, dict):
        return datos.get("datos", {}) or {}

    return {}


def extraer_respuesta_corta(resultado: Dict[str, Any]) -> str:
    if not resultado.get("ok") or not resultado.get("datos"):
        return ""

    datos = resultado["datos"]

    if isinstance(datos, dict):
        return datos.get("respuesta_corta", "") or ""

    return ""


def extraer_hallazgos(resultado: Dict[str, Any]) -> list:
    if not resultado.get("ok") or not resultado.get("datos"):
        return []

    datos = resultado["datos"]

    if isinstance(datos, dict):
        return datos.get("hallazgos_principales", []) or []

    return []


def formato_numero(valor: Any) -> str:
    if valor is None:
        return "sin dato consolidado"

    try:
        return f"{int(round(float(valor))):,}"
    except (TypeError, ValueError):
        return str(valor)


# ============================================================
# Resúmenes por componente
# ============================================================

def resumir_componente_establecimientos(resultado: Dict[str, Any]) -> Dict[str, Any]:
    datos = extraer_datos(resultado)

    return {
        "ok": resultado.get("ok"),
        "nombre": resultado.get("nombre"),
        "error": resultado.get("error"),
        "respuesta_corta": extraer_respuesta_corta(resultado),
        "limit_usado": datos.get("limit_usado"),
        "q_inicial": datos.get("q_inicial"),
        "total_registros_descargados": datos.get("total_registros_descargados"),
        "anio_usado": datos.get("anio_usado"),
        "total_registros_historicos": datos.get("total_registros_historicos"),
        "total_registros_vigencia": datos.get("total_registros_vigencia"),
        "total_establecimientos_unicos": datos.get("total_establecimientos_unicos"),
        "total_sedes_reportadas": datos.get("total_sedes_reportadas"),
        "distribucion_sector": datos.get("distribucion_sector", {}),
        "columnas_detectadas": datos.get("columnas_detectadas", {}),
        "muestra": datos.get("muestra_establecimientos", []),
    }


def resumir_componente_programas(resultado: Dict[str, Any]) -> Dict[str, Any]:
    datos = extraer_datos(resultado)

    return {
        "ok": resultado.get("ok"),
        "nombre": resultado.get("nombre"),
        "error": resultado.get("error"),
        "respuesta_corta": extraer_respuesta_corta(resultado),
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
        "columnas_detectadas": datos.get("columnas_detectadas", {}),
        "muestra": datos.get("muestra_programas", []),
    }


def resumir_componente_grupo_estadistico(resultado: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resume la salida técnica del servicio de clustering,
    pero la presenta como grupo estadístico educativo.
    """
    if not resultado.get("ok") or not resultado.get("datos"):
        return {
            "ok": False,
            "error": resultado.get("error"),
            "grupo_estadistico": None,
            "explicacion": None,
            "anio_usado": None,
            "variables_usadas": [],
            "advertencias": [],
        }

    datos = resultado["datos"]

    return {
        "ok": True,
        "error": None,
        "municipio": datos.get("municipio_consultado"),
        "departamento": datos.get("departamento"),
        "grupo_estadistico": datos.get("cluster_asignado"),
        "explicacion": datos.get("explicacion_cluster"),
        "anio_usado": datos.get("anio_usado"),
        "modelo_usado": datos.get("modelo_usado"),
        "n_grupos": datos.get("n_clusters"),
        "variables_usadas": datos.get("variables_mas_relevantes", {}).get("variables_usadas", []),
        "advertencias": datos.get("advertencias_o_limitaciones", []),
    }


def resumir_componente_similares(resultado: Dict[str, Any]) -> Dict[str, Any]:
    if not resultado.get("ok") or not resultado.get("datos"):
        return {
            "ok": False,
            "error": resultado.get("error"),
            "similares": [],
            "advertencias": [],
        }

    datos = resultado["datos"]

    return {
        "ok": True,
        "error": None,
        "anio_usado": datos.get("anio_usado"),
        "variables_usadas": datos.get("variables_usadas", []),
        "similares": datos.get("similares", []),
        "advertencias": datos.get("advertencias", []),
    }


def resumir_componente_recomendaciones(resultado: Dict[str, Any]) -> Dict[str, Any]:
    if not resultado.get("ok") or not resultado.get("datos"):
        return {
            "ok": False,
            "error": resultado.get("error"),
            "grupo_estadistico": None,
            "perfil_grupo": None,
            "recomendaciones_generales": [],
            "advertencias": [],
        }

    datos = resultado["datos"]

    return {
        "ok": True,
        "error": None,
        "grupo_estadistico": datos.get("cluster"),
        "perfil_grupo": datos.get("perfil_cluster"),
        "recomendaciones_generales": datos.get("recomendaciones_generales", []),
        "variables_usadas": datos.get("variables_usadas", []),
        "anio_usado": datos.get("anio_usado"),
        "advertencias": datos.get("advertencias", []),
    }


def resumir_componente_transito(resultado: Dict[str, Any]) -> Dict[str, Any]:
    if not resultado.get("ok") or not resultado.get("datos"):
        return {
            "ok": False,
            "nombre": resultado.get("nombre"),
            "error": resultado.get("error"),
            "respuesta_corta": "",
            "hallazgos_principales": [],
            "resumen_ejecutivo": {},
            "resumen_por_fuente": {},
            "alertas_de_lectura": [],
            "limitaciones": [],
        }

    datos = resultado["datos"]

    return {
        "ok": True,
        "nombre": resultado.get("nombre"),
        "error": None,
        "respuesta_corta": datos.get("respuesta_corta", ""),
        "hallazgos_principales": datos.get("hallazgos_principales", []),
        "resumen_ejecutivo": datos.get("resumen_ejecutivo", {}),
        "resumen_por_fuente": datos.get("resumen_por_fuente", {}),
        "alertas_de_lectura": datos.get("alertas_de_lectura", []),
        "limitaciones": datos.get("limitaciones", []),
    }


# ============================================================
# Resumen ejecutivo ciudadano
# ============================================================

def construir_resumen_ejecutivo_diagnostico(
    territorio: str,
    grupo_estadistico: Dict[str, Any],
    establecimientos: Dict[str, Any],
    programas: Dict[str, Any],
    transito: Dict[str, Any],
) -> Dict[str, Any]:
    transito_ejecutivo = transito.get("resumen_ejecutivo", {}) or {}

    return {
        "territorio": territorio,
        "grupo_estadistico_educativo": grupo_estadistico.get("grupo_estadistico"),
        "anio_grupo_estadistico": grupo_estadistico.get("anio_usado"),
        "establecimientos_unicos": establecimientos.get("total_establecimientos_unicos"),
        "sedes_reportadas": establecimientos.get("total_sedes_reportadas"),
        "anio_establecimientos": establecimientos.get("anio_usado"),
        "programas_superior_unicos": programas.get("total_programas_unicos"),
        "programas_superior_activos_unicos": programas.get("total_programas_activos_unicos"),
        "instituciones_superior_unicas": programas.get("total_instituciones_unicas"),
        "bachilleres_aproximados": transito_ejecutivo.get("bachilleres_aproximados"),
        "anio_bachilleres": transito_ejecutivo.get("anio_bachilleres"),
        "icetex_otorgados_aproximados": transito_ejecutivo.get("icetex_otorgados_aproximados"),
        "anio_icetex_otorgados": transito_ejecutivo.get("anio_icetex_otorgados"),
        "icetex_renovados_aproximados": transito_ejecutivo.get("icetex_renovados_aproximados"),
        "anio_icetex_renovados": transito_ejecutivo.get("anio_icetex_renovados"),
    }


# ============================================================
# Construcción de lectura ciudadana
# ============================================================

def construir_resumen_diagnostico(
    departamento: Optional[str],
    municipio: Optional[str],
    grupo_estadistico: Dict[str, Any],
    similares: Dict[str, Any],
    recomendaciones: Dict[str, Any],
    establecimientos: Dict[str, Any],
    programas: Dict[str, Any],
    transito: Dict[str, Any],
    limites_usados: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Construye una lectura ciudadana integrada.
    """
    territorio = municipio or departamento or "el territorio consultado"

    grupo_resumen = resumir_componente_grupo_estadistico(grupo_estadistico)
    similares_resumen = resumir_componente_similares(similares)
    recomendaciones_resumen = resumir_componente_recomendaciones(recomendaciones)
    establecimientos_resumen = resumir_componente_establecimientos(establecimientos)
    programas_resumen = resumir_componente_programas(programas)
    transito_resumen = resumir_componente_transito(transito)

    resumen_ejecutivo = construir_resumen_ejecutivo_diagnostico(
        territorio=territorio,
        grupo_estadistico=grupo_resumen,
        establecimientos=establecimientos_resumen,
        programas=programas_resumen,
        transito=transito_resumen,
    )

    hallazgos = []

    # --------------------------------------------------------
    # Grupo estadístico educativo
    # --------------------------------------------------------
    if grupo_resumen.get("ok"):
        hallazgos.append(
            f"{territorio} pertenece al grupo estadístico {grupo_resumen.get('grupo_estadistico')} "
            "de municipios con comportamiento educativo similar, según los indicadores municipales disponibles."
        )

        if grupo_resumen.get("explicacion"):
            hallazgos.append(grupo_resumen["explicacion"])

    elif municipio:
        hallazgos.append(
            f"No fue posible calcular el grupo estadístico educativo para {territorio}: "
            f"{grupo_resumen.get('error')}"
        )

    else:
        hallazgos.append(
            "No se calculó grupo estadístico educativo porque la consulta es departamental. "
            "La agrupación estadística se calcula a nivel municipal."
        )

    # --------------------------------------------------------
    # Municipios similares
    # --------------------------------------------------------
    if similares_resumen.get("ok") and similares_resumen.get("similares"):
        nombres = [
            f"{item.get('municipio')} ({item.get('departamento')})"
            for item in similares_resumen["similares"][:5]
        ]

        hallazgos.append(
            "Municipios con mayor similitud estadística: " + ", ".join(nombres) + "."
        )

    elif municipio:
        hallazgos.append(
            f"No se consolidó una lista de municipios similares para {territorio}: "
            f"{similares_resumen.get('error')}"
        )

    # --------------------------------------------------------
    # Establecimientos
    # --------------------------------------------------------
    if establecimientos_resumen.get("ok"):
        total_est = establecimientos_resumen.get("total_establecimientos_unicos")
        anio_est = establecimientos_resumen.get("anio_usado")
        sedes = establecimientos_resumen.get("total_sedes_reportadas")
        registros_vigencia = establecimientos_resumen.get("total_registros_vigencia")
        registros_historicos = establecimientos_resumen.get("total_registros_historicos")

        if total_est is not None:
            texto = (
                f"En establecimientos educativos, se estimaron "
                f"{formato_numero(total_est)} establecimientos únicos"
            )

            if anio_est:
                texto += f" para la vigencia {anio_est}"

            if sedes is not None:
                texto += f", con aproximadamente {formato_numero(sedes)} sedes reportadas"

            if registros_vigencia is not None:
                texto += f". Registros analizados en la vigencia: {formato_numero(registros_vigencia)}"

            if registros_historicos is not None:
                texto += f"; registros históricos filtrados: {formato_numero(registros_historicos)}"

            texto += "."

            hallazgos.append(texto)

        distribucion_sector = establecimientos_resumen.get("distribucion_sector", {})

        if distribucion_sector:
            sectores = ", ".join(
                f"{sector}: {cantidad}"
                for sector, cantidad in distribucion_sector.items()
            )
            hallazgos.append(f"Distribución de establecimientos por sector: {sectores}.")

    else:
        hallazgos.append(
            f"No fue posible consolidar establecimientos educativos para {territorio}: "
            f"{establecimientos_resumen.get('error')}"
        )

    # --------------------------------------------------------
    # Programas de educación superior
    # --------------------------------------------------------
    if programas_resumen.get("ok"):
        total_programas = programas_resumen.get("total_programas_unicos")
        total_programas_activos = programas_resumen.get("total_programas_activos_unicos")
        total_instituciones = programas_resumen.get("total_instituciones_unicas")
        total_registros = programas_resumen.get("total_registros")

        hallazgos.append(
            f"En oferta de educación superior, se estimaron "
            f"{formato_numero(total_programas or 0)} programas únicos en "
            f"{formato_numero(total_instituciones or 0)} instituciones "
            f"a partir de {formato_numero(total_registros or 0)} registros."
        )

        if total_programas_activos is not None:
            hallazgos.append(
                f"De esos programas, aproximadamente {formato_numero(total_programas_activos)} "
                "aparecen como activos según la columna de estado detectada."
            )

        metodologias = programas_resumen.get("distribucion_metodologia", [])

        if metodologias:
            principales = ", ".join(
                f"{item.get('valor')}: {item.get('conteo')}"
                for item in metodologias[:3]
            )
            hallazgos.append(
                f"Metodologías o modalidades más frecuentes en la oferta detectada: {principales}."
            )

        niveles = programas_resumen.get("distribucion_nivel", [])

        if niveles:
            principales_niveles = ", ".join(
                f"{item.get('valor')}: {item.get('conteo')}"
                for item in niveles[:3]
            )
            hallazgos.append(
                f"Niveles académicos más frecuentes: {principales_niveles}."
            )

    else:
        hallazgos.append(
            f"No fue posible consolidar programas de educación superior para {territorio}: "
            f"{programas_resumen.get('error')}"
        )

    # --------------------------------------------------------
    # Tránsito educativo
    # --------------------------------------------------------
    if transito_resumen.get("ok"):
        hallazgos_transito = transito_resumen.get("hallazgos_principales", [])
        hallazgos.extend(hallazgos_transito[:7])
    else:
        hallazgos.append(
            f"No fue posible consolidar el cruce de tránsito educativo para {territorio}: "
            f"{transito_resumen.get('error')}"
        )

    # --------------------------------------------------------
    # Recomendaciones exploratorias
    # --------------------------------------------------------
    if recomendaciones_resumen.get("ok"):
        recs = recomendaciones_resumen.get("recomendaciones_generales", [])

        if recs:
            hallazgos.append(
                "Recomendaciones exploratorias sugeridas: " + " ".join(recs[:3])
            )

    elif municipio:
        hallazgos.append(
            f"No fue posible generar recomendaciones por grupo estadístico para {territorio}: "
            f"{recomendaciones_resumen.get('error')}"
        )

    limitaciones = [
        "Este diagnóstico es exploratorio y depende de la disponibilidad de datos abiertos.",
        "La agrupación estadística identifica similitudes entre municipios, no causalidad ni calidad educativa definitiva.",
        "Los conteos son estimaciones basadas en columnas detectadas automáticamente.",
        "Algunos datasets pueden tener columnas, nombres territoriales o vigencias diferentes.",
        "Las vigencias de establecimientos, bachilleres, programas e ICETEX pueden no coincidir.",
        "Para consultas departamentales se usan límites altos de registros para reducir sesgos por muestra parcial.",
        "La información debe contrastarse con fuentes institucionales y conocimiento territorial local."
    ]

    sugerencias = [
        f"¿Qué recomendaciones educativas específicas tiene {territorio}?",
        f"¿Qué municipios se parecen a {territorio}?",
        f"¿Qué programas de educación superior aparecen en {territorio}?",
        f"¿Cómo se relacionan bachilleres, educación superior e ICETEX en {territorio}?"
    ]

    return {
        "respuesta_corta": (
            f"Se construyó un diagnóstico educativo exploratorio para {territorio}, "
            "integrando establecimientos educativos, oferta de educación superior, tránsito educativo "
            "y, cuando aplica, grupos de municipios con comportamiento educativo similar."
        ),
        "resumen_ejecutivo": resumen_ejecutivo,
        "hallazgos_integrados": hallazgos,
        "limitaciones": limitaciones,
        "sugerencias_de_siguiente_pregunta": sugerencias,
        "metadatos_procesamiento": {
            "escala": limites_usados.get("escala"),
            "limit_solicitado": limites_usados.get("limit_solicitado"),
            "limit_minimo_aplicado": limites_usados.get("limit_minimo_aplicado"),
            "limit_maximo_permitido": limites_usados.get("limit_maximo_permitido"),
            "limit_final": limites_usados.get("limit_final"),
        }
    }


# ============================================================
# Servicio principal
# ============================================================

def diagnostico_territorial_educativo_service(
    departamento: Optional[str] = None,
    municipio: Optional[str] = None,
    limit: int = DEFAULT_ANALYTIC_LIMIT
) -> Dict[str, Any]:
    """
    Diagnóstico territorial educativo integral.

    Integra:
    - grupo estadístico municipal,
    - municipios similares,
    - recomendaciones exploratorias,
    - establecimientos educativos,
    - programas de educación superior,
    - tránsito educativo: bachilleres + educación superior + ICETEX.
    """

    if not departamento and not municipio:
        raise ValueError(
            "Debes indicar al menos un departamento o municipio para generar el diagnóstico territorial."
        )

    limites = resolver_limites_diagnostico(
        departamento=departamento,
        municipio=municipio,
        limit=limit
    )

    limit_agrupacion = limites["limit_agrupacion_estadistica"]
    limit_descriptivo = limites["limit_descriptivo"]
    limit_transito = limites["limit_transito"]

    if municipio:
        grupo_estadistico = ejecutar_seguro(
            "grupo_estadistico_educativo",
            consultar_cluster_municipio_service,
            departamento=departamento,
            municipio=municipio,
            limit=limit_agrupacion
        )

        similares = ejecutar_seguro(
            "municipios_similares",
            buscar_municipios_similares_service,
            departamento=departamento,
            municipio=municipio,
            top_n=5,
            limit=limit_agrupacion
        )

        recomendaciones = ejecutar_seguro(
            "recomendaciones",
            generar_recomendaciones_municipio_service,
            departamento=departamento,
            municipio=municipio,
            limit=limit_agrupacion
        )

    else:
        grupo_estadistico = {
            "ok": False,
            "nombre": "grupo_estadistico_educativo",
            "datos": None,
            "error": "No se calcula grupo estadístico porque no se indicó municipio."
        }

        similares = {
            "ok": False,
            "nombre": "municipios_similares",
            "datos": None,
            "error": "No se calculan municipios similares porque no se indicó municipio."
        }

        recomendaciones = {
            "ok": False,
            "nombre": "recomendaciones",
            "datos": None,
            "error": "No se generan recomendaciones por grupo estadístico porque no se indicó municipio."
        }

    establecimientos = ejecutar_seguro(
        "establecimientos_educativos",
        consultar_establecimientos_educativos_service,
        departamento=departamento,
        municipio=municipio,
        limit=limit_descriptivo
    )

    programas = ejecutar_seguro(
        "programas_superior",
        consultar_programas_superior_service,
        departamento=departamento,
        municipio=municipio,
        texto=None,
        limit=limit_descriptivo
    )

    transito = ejecutar_seguro(
        "transito_educativo",
        analizar_transito_educativo_service,
        departamento=departamento,
        municipio=municipio,
        limit=limit_transito
    )

    resumen = construir_resumen_diagnostico(
        departamento=departamento,
        municipio=municipio,
        grupo_estadistico=grupo_estadistico,
        similares=similares,
        recomendaciones=recomendaciones,
        establecimientos=establecimientos,
        programas=programas,
        transito=transito,
        limites_usados=limites
    )

    return {
        "tipo_analisis": "diagnostico_territorial_educativo",
        "territorio_consultado": {
            "departamento": departamento,
            "municipio": municipio
        },
        "limites_usados": limites,
        "respuesta_ciudadana": resumen,
        "componentes": {
            "grupo_estadistico_educativo": resumir_componente_grupo_estadistico(grupo_estadistico),
            "municipios_similares": resumir_componente_similares(similares),
            "recomendaciones": resumir_componente_recomendaciones(recomendaciones),
            "establecimientos_educativos": resumir_componente_establecimientos(establecimientos),
            "programas_superior": resumir_componente_programas(programas),
            "transito_educativo": resumir_componente_transito(transito)
        },
        "fuentes_usadas": [
            {
                "dataset_key": "estadisticas_municipio",
                "nombre": "MEN - Estadísticas en educación preescolar, básica y media por municipio",
                "url": "https://www.datos.gov.co/resource/nudc-7mev.json"
            },
            {
                "dataset_key": "establecimientos_educativos",
                "nombre": "MEN - Establecimientos educativos",
                "url": "https://www.datos.gov.co/resource/cfw5-qzt5.json"
            },
            {
                "dataset_key": "programas_superior",
                "nombre": "Programas de educación superior",
                "url": "https://www.datos.gov.co/resource/upr9-nkiz.json"
            },
            {
                "dataset_key": "bachilleres",
                "nombre": "Número de bachilleres por ETC",
                "url": "https://www.datos.gov.co/resource/5c2k-ahfc.json"
            },
            {
                "dataset_key": "icetex_otorgados",
                "nombre": "Créditos ICETEX otorgados",
                "url": "https://www.datos.gov.co/resource/26bn-e42j.json"
            },
            {
                "dataset_key": "icetex_renovados",
                "nombre": "Créditos ICETEX renovados",
                "url": "https://www.datos.gov.co/resource/nvcf-b8a3.json"
            }
        ],
        "nota_para_gpt": (
            "Usa respuesta_ciudadana como síntesis principal. "
            "Usa componentes como evidencia. "
            "Explica que el diagnóstico es exploratorio, no causal ni definitivo. "
            "Presenta el clustering como grupo estadístico de municipios con comportamiento educativo similar. "
            "Los límites usados aparecen en limites_usados."
        )
    }