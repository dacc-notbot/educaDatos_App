from typing import Any, Dict, List, Optional
from collections import Counter

from services.socrata_service import (
    consultar_dataset,
    normalizar_texto,
    seleccionar_columna_por_patrones,
)

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

def limpiar_valor(valor: Any) -> str:
    if valor is None:
        return ""

    texto = str(valor).strip()

    if texto.lower() in ["none", "null", "nan", ""]:
        return ""

    return texto


def valor_a_numero(valor: Any) -> Optional[float]:
    if valor is None:
        return None

    texto = str(valor).strip()

    if texto == "":
        return None

    texto = texto.replace("%", "")
    texto = texto.replace(".", "")
    texto = texto.replace(",", ".")

    permitido = "0123456789.-"
    texto = "".join(c for c in texto if c in permitido)

    if texto in ["", "-", ".", "-."]:
        return None

    try:
        return float(texto)
    except ValueError:
        return None


def resolver_limit_bachilleres(
    departamento: Optional[str],
    municipio: Optional[str],
    limit: Optional[int]
) -> int:
    """
    Define límites amplios para consultas de bachilleres.

    - Departamento completo: mínimo alto para reducir sesgo por muestra parcial.
    - Municipio o ETC: mínimo alto porque el dataset puede tener registros históricos.
    - Nunca supera MAX_LIMIT.
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


def texto_completo_registro(registro: Dict[str, Any]) -> str:
    return normalizar_texto(" ".join(str(valor) for valor in registro.values()))


def registro_coincide_territorio(
    registro: Dict[str, Any],
    departamento: Optional[str],
    municipio: Optional[str],
    col_departamento: Optional[str],
    col_municipio: Optional[str],
    col_secretaria: Optional[str]
) -> bool:
    """
    Filtra territorio.

    En bachilleres muchas veces el dato viene por ETC o secretaría,
    no siempre por municipio exacto. Por eso se revisa municipio, secretaría
    y texto completo como respaldo.
    """
    texto_completo = texto_completo_registro(registro)

    if departamento:
        departamento_norm = normalizar_texto(departamento)

        if col_departamento:
            valor_departamento = normalizar_texto(registro.get(col_departamento))
            if valor_departamento != departamento_norm:
                return False
        elif departamento_norm not in texto_completo:
            return False

    if municipio:
        municipio_norm = normalizar_texto(municipio)

        coincide_municipio = False
        coincide_secretaria = False
        coincide_texto = municipio_norm in texto_completo

        if col_municipio:
            coincide_municipio = (
                normalizar_texto(registro.get(col_municipio)) == municipio_norm
            )

        if col_secretaria:
            coincide_secretaria = (
                municipio_norm in normalizar_texto(registro.get(col_secretaria))
            )

        if not coincide_municipio and not coincide_secretaria and not coincide_texto:
            return False

    return True


def filtrar_por_vigencia_mas_reciente(
    registros: List[Dict[str, Any]],
    col_anio: Optional[str]
) -> tuple[List[Dict[str, Any]], Optional[int]]:
    if not registros or not col_anio:
        return registros, None

    anios = []

    for registro in registros:
        numero = valor_a_numero(registro.get(col_anio))

        if numero is not None:
            anios.append(int(numero))

    if not anios:
        return registros, None

    anio_reciente = max(anios)

    filtrados = [
        registro
        for registro in registros
        if valor_a_numero(registro.get(col_anio)) == anio_reciente
    ]

    return filtrados, anio_reciente


def sumar_columna(
    registros: List[Dict[str, Any]],
    columna: Optional[str]
) -> Optional[float]:
    if not registros or not columna:
        return None

    total = 0
    encontrados = 0

    for registro in registros:
        numero = valor_a_numero(registro.get(columna))

        if numero is not None:
            total += numero
            encontrados += 1

    if encontrados == 0:
        return None

    return total


def es_columna_numerica_confiable(
    registros: List[Dict[str, Any]],
    columna: Optional[str],
    minimo_ratio: float = 0.6
) -> bool:
    """
    Verifica que la columna seleccionada pueda sumarse con confianza.
    """
    if not registros or not columna:
        return False

    valores = [
        limpiar_valor(registro.get(columna))
        for registro in registros[:200]
        if limpiar_valor(registro.get(columna))
    ]

    if not valores:
        return False

    numericos = [
        valor_a_numero(valor)
        for valor in valores
    ]

    numericos_validos = [
        valor
        for valor in numericos
        if valor is not None
    ]

    ratio = len(numericos_validos) / len(valores)

    return ratio >= minimo_ratio


def distribucion_por_columna(
    registros: List[Dict[str, Any]],
    columna: Optional[str],
    top_n: int = 10
) -> List[Dict[str, Any]]:
    if not registros or not columna:
        return []

    contador = Counter()

    for registro in registros:
        valor = limpiar_valor(registro.get(columna)) or "SIN DATO"
        contador[valor] += 1

    return [
        {
            "valor": valor,
            "conteo": conteo
        }
        for valor, conteo in contador.most_common(top_n)
    ]


def construir_muestra_bachilleres(
    registros: List[Dict[str, Any]],
    col_departamento: Optional[str],
    col_municipio: Optional[str],
    col_secretaria: Optional[str],
    col_anio: Optional[str],
    col_bachilleres: Optional[str],
    max_items: int = 10
) -> List[Dict[str, Any]]:
    muestra = []

    for registro in registros[:max_items]:
        item = {}

        if col_departamento:
            valor = limpiar_valor(registro.get(col_departamento))
            if valor:
                item["departamento"] = valor

        if col_municipio:
            valor = limpiar_valor(registro.get(col_municipio))
            if valor:
                item["municipio"] = valor

        if col_secretaria:
            valor = limpiar_valor(registro.get(col_secretaria))
            if valor:
                item["secretaria_o_etc"] = valor

        if col_anio:
            valor = limpiar_valor(registro.get(col_anio))
            if valor:
                item["anio"] = valor

        if col_bachilleres:
            valor = limpiar_valor(registro.get(col_bachilleres))
            if valor:
                item["bachilleres_o_aprobados"] = valor

        if not item:
            for campo, valor in list(registro.items())[:8]:
                valor_limpio = limpiar_valor(valor)
                if valor_limpio:
                    item[campo] = valor_limpio

        muestra.append(item)

    return muestra


# ============================================================
# Servicio principal
# ============================================================

def consultar_bachilleres_service(
    departamento: Optional[str] = None,
    municipio: Optional[str] = None,
    limit: int = DEFAULT_ANALYTIC_LIMIT
) -> Dict[str, Any]:
    """
    Consulta bachilleres o egresados de educación media.

    Usa filtros flexibles porque el dataset puede venir por ETC, secretaría,
    municipio, departamento o vigencia.

    Para consultas departamentales evita $q y filtra localmente con volumen amplio,
    porque $q puede traer una muestra parcial.
    """

    if not departamento and not municipio:
        raise ValueError(
            "Debes indicar al menos un departamento o municipio para consultar bachilleres."
        )

    limit_final = resolver_limit_bachilleres(
        departamento=departamento,
        municipio=municipio,
        limit=limit
    )

    # Para municipio, $q ayuda a ubicar rápido la ETC o municipio.
    # Para departamento completo, evitamos $q para reducir sesgo por muestra parcial.
    q_inicial = municipio if municipio else None

    registros = consultar_dataset(
        dataset_key="bachilleres",
        limit=limit_final,
        q=q_inicial
    )

    fuente = {
        "dataset_key": "bachilleres",
        "nombre": "Número de bachilleres por entidad territorial certificada",
        "url": "https://www.datos.gov.co/resource/5c2k-ahfc.json"
    }

    if not registros:
        territorio = municipio or departamento

        return {
            "tipo_consulta": "bachilleres",
            "territorio_consultado": {
                "departamento": departamento,
                "municipio": municipio
            },
            "respuesta_corta": (
                f"No encontré registros de bachilleres para {territorio} "
                "con los filtros usados."
            ),
            "hallazgos_principales": [
                "No se encontraron registros en la consulta inicial.",
                "Puedes intentar con el nombre del departamento, municipio o entidad territorial certificada."
            ],
            "datos": {
                "limit_usado": limit_final,
                "q_inicial": q_inicial,
                "total_registros_descargados": 0,
                "anio_usado": None,
                "total_registros_historicos": 0,
                "total_registros_vigencia": 0,
                "total_bachilleres_aproximado": None,
                "distribucion_secretaria_o_etc": [],
                "columnas_detectadas": {},
                "muestra_bachilleres": []
            },
            "fuentes_usadas": [fuente],
            "limitaciones": [
                "La ausencia de resultados puede deberse a diferencias en la forma como está registrada la ETC o secretaría."
            ],
            "sugerencias_de_siguiente_pregunta": [
                f"¿Cuántos bachilleres hay en {territorio}?",
                f"¿Cómo se relacionan bachilleres, educación superior e ICETEX en {territorio}?",
                f"¿Qué oportunidades de educación superior hay para los bachilleres de {territorio}?"
            ]
        }

    col_departamento = seleccionar_columna_por_patrones(
        registros,
        ["departamento", "nombre_departamento", "nom_departamento"],
        excluir=["codigo", "cod", "id"]
    )

    col_municipio = seleccionar_columna_por_patrones(
        registros,
        ["municipio", "nombre_municipio", "nom_municipio"],
        excluir=["codigo", "cod", "id"]
    )

    col_secretaria = seleccionar_columna_por_patrones(
        registros,
        [
            "secretaria",
            "secretaría",
            "entidad_territorial",
            "entidad territorial",
            "entidad_territorial_certificada",
            "entidad territorial certificada",
            "etc",
            "nombre_etc"
        ],
        excluir=["codigo", "cod", "id"]
    )

    col_anio = seleccionar_columna_por_patrones(
        registros,
        ["a_o", "ano", "anio", "año", "vigencia", "periodo"],
        excluir=["codigo", "cod", "id"]
    )

    col_bachilleres = seleccionar_columna_por_patrones(
        registros,
        [
            "aprobados_11_total",
            "aprobados grado 11 total",
            "aprobados_grado_11_total",
            "aprobados_total_grado_11",
            "total_aprobados_11",
            "grado_11_total",
            "grado 11 total",
            "bachilleres_total",
            "total_bachilleres",
            "egresados_total",
            "graduados_total",
            "aprobados_total",
            "total"
        ],
        excluir=[
            "codigo", "cod", "id",
            "porcentaje", "tasa",
            "oficial", "no_oficial",
            "hombre", "mujer",
            "edad", "zona", "sector",
            "departamento", "municipio", "secretaria", "secretaría",
            "periodo", "anio", "año", "ano"
        ]
    )

    registros_filtrados = [
        registro
        for registro in registros
        if registro_coincide_territorio(
            registro=registro,
            departamento=departamento,
            municipio=municipio,
            col_departamento=col_departamento,
            col_municipio=col_municipio,
            col_secretaria=col_secretaria
        )
    ]

    registros_vigencia, anio_usado = filtrar_por_vigencia_mas_reciente(
        registros_filtrados,
        col_anio
    )

    if not es_columna_numerica_confiable(registros_vigencia, col_bachilleres):
        col_bachilleres = None

    total_registros_historicos = len(registros_filtrados)
    total_registros_vigencia = len(registros_vigencia)

    total_bachilleres = sumar_columna(
        registros=registros_vigencia,
        columna=col_bachilleres
    )

    distribucion_secretaria = distribucion_por_columna(
        registros_vigencia,
        col_secretaria
    )

    muestra = construir_muestra_bachilleres(
        registros=registros_vigencia,
        col_departamento=col_departamento,
        col_municipio=col_municipio,
        col_secretaria=col_secretaria,
        col_anio=col_anio,
        col_bachilleres=col_bachilleres
    )

    territorio = municipio or departamento
    texto_anio = f" en la vigencia más reciente detectada ({anio_usado})" if anio_usado else ""

    if total_bachilleres is not None:
        respuesta_corta = (
            f"Para {territorio}, encontré una suma aproximada de {round(total_bachilleres):,} "
            f"bachilleres o egresados de educación media{texto_anio}, según la columna detectada "
            "en el dataset."
        )
    else:
        respuesta_corta = (
            f"Para {territorio}, encontré {total_registros_vigencia} registros relacionados "
            f"con bachilleres{texto_anio}. No se identificó una columna numérica confiable "
            "para sumar bachilleres, por lo que se reportan registros disponibles."
        )

    hallazgos = [
        f"Se filtró el dataset de bachilleres para {territorio}.",
        (
            f"Se usó la vigencia más reciente disponible: {anio_usado}."
            if anio_usado
            else "No se pudo detectar una columna de vigencia; se usaron los registros disponibles."
        ),
        f"Registros descargados desde datos.gov.co: {len(registros)}.",
        f"Registros históricos encontrados antes de filtrar por vigencia: {total_registros_historicos}.",
        f"Registros analizados después del filtro de vigencia: {total_registros_vigencia}.",
        (
            f"Columna usada para estimar bachilleres: {col_bachilleres}."
            if col_bachilleres
            else "No se detectó una columna numérica confiable para sumar bachilleres."
        )
    ]

    if total_bachilleres is not None:
        hallazgos.append(
            f"Suma aproximada de bachilleres o egresados en la vigencia analizada: {round(total_bachilleres):,}."
        )

    if distribucion_secretaria:
        secretarias = ", ".join(
            f"{item['valor']}: {item['conteo']}"
            for item in distribucion_secretaria[:5]
        )
        hallazgos.append(f"Distribución por secretaría o ETC: {secretarias}.")

    return {
        "tipo_consulta": "bachilleres",
        "territorio_consultado": {
            "departamento": departamento,
            "municipio": municipio
        },
        "respuesta_corta": respuesta_corta,
        "hallazgos_principales": hallazgos,
        "datos": {
            "limit_usado": limit_final,
            "q_inicial": q_inicial,
            "total_registros_descargados": len(registros),
            "anio_usado": anio_usado,
            "total_registros_historicos": total_registros_historicos,
            "total_registros_vigencia": total_registros_vigencia,
            "total_bachilleres_aproximado": (
                round(total_bachilleres) if total_bachilleres is not None else None
            ),
            "distribucion_secretaria_o_etc": distribucion_secretaria,
            "columnas_detectadas": {
                "departamento": col_departamento,
                "municipio": col_municipio,
                "secretaria_o_etc": col_secretaria,
                "anio": col_anio,
                "bachilleres": col_bachilleres
            },
            "muestra_bachilleres": muestra
        },
        "fuentes_usadas": [fuente],
        "limitaciones": [
            "El conteo es aproximado y depende de la columna numérica detectada en el dataset.",
            "Si no se detecta una columna numérica confiable, se reporta el número de registros disponibles en la vigencia.",
            "El dataset puede estar organizado por entidad territorial certificada, secretaría, municipio o vigencia.",
            "Los registros históricos no equivalen necesariamente al dato actual de bachilleres.",
            "La lectura es descriptiva y no prueba causas sobre acceso o continuidad educativa.",
            "Para consultas departamentales se evita usar búsqueda textual inicial cuando puede sesgar la muestra; por eso se descargan más registros y se filtra localmente."
        ],
        "sugerencias_de_siguiente_pregunta": [
            f"¿Cómo se relacionan bachilleres, educación superior e ICETEX en {territorio}?",
            f"¿Qué programas de educación superior hay para los bachilleres de {territorio}?",
            f"¿Qué créditos ICETEX aparecen asociados a {territorio}?"
        ]
    }