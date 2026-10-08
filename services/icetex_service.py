from utils.normalizacion import valor_a_numero
from typing import Any, Dict, List, Optional
from collections import Counter

from services.socrata_service import (
    normalizar_texto,
)

from config import MAX_LIMIT, DEFAULT_ANALYTIC_LIMIT, MIN_LIMIT_MUNICIPAL, MIN_LIMIT_DEPARTAMENTAL


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




def resolver_limit_icetex(
    departamento: Optional[str],
    municipio: Optional[str],
    limit: Optional[int]
) -> int:
    """
    Define límites amplios para consultas ICETEX.

    - Departamento completo: mínimo alto para reducir sesgo por muestra parcial.
    - Municipio: mínimo alto porque puede haber registros históricos.
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
    col_municipio: Optional[str]
) -> bool:
    texto_completo = None

    if departamento:
        dep_norm = normalizar_texto(departamento)

        if col_departamento:
            if normalizar_texto(registro.get(col_departamento)) != dep_norm:
                return False
        else:
            if texto_completo is None:
                texto_completo = texto_completo_registro(registro)
            if dep_norm not in texto_completo:
                return False

    if municipio:
        mun_norm = normalizar_texto(municipio)

        if col_municipio:
            if normalizar_texto(registro.get(col_municipio)) != mun_norm:
                return False
        else:
            if texto_completo is None:
                texto_completo = texto_completo_registro(registro)
            if mun_norm not in texto_completo:
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


def es_columna_numerica_confiable(
    registros: List[Dict[str, Any]],
    columna: Optional[str],
    minimo_ratio: float = 0.6
) -> bool:
    """
    Verifica que la columna seleccionada pueda sumarse con confianza.

    Evita errores como sumar valores romanos, estratos, niveles,
    categorías o campos que parecen numéricos pero no representan créditos.
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

    valores_romanos = {
        "I", "II", "III", "IV", "V",
        "VI", "VII", "VIII", "IX", "X"
    }

    if any(valor.upper() in valores_romanos for valor in valores):
        return False

    convertidos = [valor_a_numero(valor) for valor in valores]
    numericos = [valor for valor in convertidos if valor is not None]

    ratio = len(numericos) / len(valores)

    return ratio >= minimo_ratio


def construir_muestra_icetex(
    registros: List[Dict[str, Any]],
    col_departamento: Optional[str],
    col_municipio: Optional[str],
    col_anio: Optional[str],
    col_numero: Optional[str],
    col_linea: Optional[str],
    col_institucion: Optional[str],
    col_sector: Optional[str],
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

        if col_anio:
            valor = limpiar_valor(registro.get(col_anio))
            if valor:
                item["anio"] = valor

        if col_numero:
            valor = limpiar_valor(registro.get(col_numero))
            if valor:
                item["creditos_o_beneficiarios"] = valor

        if col_linea:
            valor = limpiar_valor(registro.get(col_linea))
            if valor:
                item["linea_o_modalidad"] = valor

        if col_institucion:
            valor = limpiar_valor(registro.get(col_institucion))
            if valor:
                item["institucion"] = valor

        if col_sector:
            valor = limpiar_valor(registro.get(col_sector))
            if valor:
                item["sector_o_naturaleza"] = valor

        if not item:
            for campo, valor in list(registro.items())[:8]:
                valor_limpio = limpiar_valor(valor)
                if valor_limpio:
                    item[campo] = valor_limpio

        muestra.append(item)

    return muestra


def obtener_configuracion_icetex(tipo: str) -> Dict[str, str]:
    tipo_normalizado = normalizar_texto(tipo)

    if "renov" in tipo_normalizado:
        return {
            "dataset_key": "icetex_renovados",
            "nombre_fuente": "Créditos renovados por ICETEX",
            "url_fuente": "https://www.datos.gov.co/resource/nvcf-b8a3.json",
            "etiqueta_tipo": "renovados"
        }

    return {
        "dataset_key": "icetex_otorgados",
        "nombre_fuente": "Créditos otorgados por ICETEX",
        "url_fuente": "https://www.datos.gov.co/resource/26bn-e42j.json",
        "etiqueta_tipo": "otorgados"
    }


# ============================================================
# Servicio principal
# ============================================================

def consultar_icetex_service(
    departamento: Optional[str] = None,
    municipio: Optional[str] = None,
    tipo: str = "otorgados",
    limit: int = DEFAULT_ANALYTIC_LIMIT,
    anio: Optional[int] = None,
    filtros: Optional[Dict[str, str]] = None,
    *,
    _plazo: Optional[float] = None,
) -> Dict[str, Any]:
    # Las sumas se calculan sobre toda la fuente, sin limitar filas individuales.
    from services.estadisticas_icetex import consultar_estadisticas_icetex
    return consultar_estadisticas_icetex(departamento, municipio, tipo, anio, filtros, _plazo=_plazo)
