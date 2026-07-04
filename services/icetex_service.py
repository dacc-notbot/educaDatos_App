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
    texto_completo = texto_completo_registro(registro)

    if departamento:
        dep_norm = normalizar_texto(departamento)

        if col_departamento:
            if normalizar_texto(registro.get(col_departamento)) != dep_norm:
                return False
        elif dep_norm not in texto_completo:
            return False

    if municipio:
        mun_norm = normalizar_texto(municipio)

        if col_municipio:
            if normalizar_texto(registro.get(col_municipio)) != mun_norm:
                return False
        elif mun_norm not in texto_completo:
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
    limit: int = DEFAULT_ANALYTIC_LIMIT
) -> Dict[str, Any]:
    """
    Consulta créditos ICETEX otorgados o renovados.

    tipo:
    - otorgados
    - renovados

    Para consultas departamentales evita $q y filtra localmente con volumen amplio,
    porque $q puede traer una muestra parcial.
    """

    if not departamento and not municipio:
        raise ValueError(
            "Debes indicar al menos un departamento o municipio para consultar créditos ICETEX."
        )

    config_icetex = obtener_configuracion_icetex(tipo)

    dataset_key = config_icetex["dataset_key"]
    nombre_fuente = config_icetex["nombre_fuente"]
    url_fuente = config_icetex["url_fuente"]
    etiqueta_tipo = config_icetex["etiqueta_tipo"]

    limit_final = resolver_limit_icetex(
        departamento=departamento,
        municipio=municipio,
        limit=limit
    )

    # Para municipio, $q ayuda a ubicar registros.
    # Para departamento completo, se evita $q para reducir sesgo por muestra parcial.
    q_inicial = municipio if municipio else None

    registros = consultar_dataset(
        dataset_key=dataset_key,
        limit=limit_final,
        q=q_inicial
    )

    fuente = {
        "dataset_key": dataset_key,
        "nombre": nombre_fuente,
        "url": url_fuente
    }

    if not registros:
        territorio = municipio or departamento

        return {
            "tipo_consulta": f"icetex_{etiqueta_tipo}",
            "territorio_consultado": {
                "departamento": departamento,
                "municipio": municipio,
                "tipo": etiqueta_tipo
            },
            "respuesta_corta": (
                f"No encontré registros de créditos ICETEX {etiqueta_tipo} "
                f"para {territorio} con los filtros usados."
            ),
            "hallazgos_principales": [
                "No se encontraron registros en la consulta inicial.",
                "Puedes intentar con el nombre del departamento, municipio o institución."
            ],
            "datos": {
                "limit_usado": limit_final,
                "q_inicial": q_inicial,
                "anio_usado": None,
                "tipo_credito": etiqueta_tipo,
                "total_registros_descargados": 0,
                "total_registros_historicos": 0,
                "total_registros_vigencia": 0,
                "total_creditos_o_beneficiarios_aproximado": None,
                "lineas_o_modalidades_frecuentes": [],
                "instituciones_frecuentes": [],
                "sectores_frecuentes": [],
                "columnas_detectadas": {},
                "muestra_icetex": []
            },
            "fuentes_usadas": [fuente],
            "limitaciones": [
                "La ausencia de resultados puede depender de la forma como está registrado el territorio en el dataset."
            ],
            "sugerencias_de_siguiente_pregunta": [
                f"¿Qué créditos ICETEX hay en {territorio}?",
                f"¿Cómo se relaciona ICETEX con bachilleres y educación superior en {territorio}?",
                f"¿Qué programas de educación superior hay en {territorio}?"
            ]
        }

    col_departamento = seleccionar_columna_por_patrones(
        registros,
        [
            "departamento",
            "nombre_departamento",
            "nom_departamento",
            "depto",
            "departamento_residencia",
            "departamento_beneficiario",
            "departamento_institucion"
        ],
        excluir=["codigo", "cod", "id"]
    )

    col_municipio = seleccionar_columna_por_patrones(
        registros,
        [
            "municipio",
            "ciudad",
            "nombre_municipio",
            "nom_municipio",
            "municipio_residencia",
            "municipio_beneficiario",
            "municipio_institucion"
        ],
        excluir=["codigo", "cod", "id"]
    )

    col_anio = seleccionar_columna_por_patrones(
        registros,
        [
            "a_o",
            "ano",
            "anio",
            "año",
            "vigencia",
            "periodo",
            "year"
        ],
        excluir=["codigo", "cod", "id"]
    )

    col_numero = seleccionar_columna_por_patrones(
        registros,
        [
            "total_creditos",
            "total créditos",
            "numero_creditos",
            "número_creditos",
            "número créditos",
            "cantidad_creditos",
            "cantidad créditos",
            "beneficiarios_total",
            "total_beneficiarios",
            "numero_beneficiarios",
            "número_beneficiarios",
            "número beneficiarios",
            "cantidad_beneficiarios",
            "creditos",
            "créditos",
            "beneficiarios",
            "total",
            "cantidad"
        ],
        excluir=[
            "codigo", "cod", "id",
            "estrato", "quintil",
            "categoria", "categoría",
            "nivel", "semestre",
            "periodo", "a_o", "ano", "anio", "año", "year",
            "rango", "sexo", "sector",
            "oficial", "privado", "naturaleza",
            "departamento", "municipio", "ciudad",
            "linea", "línea", "modalidad",
            "institucion", "institución", "ies"
        ]
    )

    col_linea = seleccionar_columna_por_patrones(
        registros,
        [
            "linea",
            "línea",
            "modalidad",
            "tipo_credito",
            "tipo crédito",
            "programa_credito",
            "programa crédito",
            "nivel_credito"
        ],
        excluir=["codigo", "cod", "id"]
    )

    col_institucion = seleccionar_columna_por_patrones(
        registros,
        [
            "nombre_institucion",
            "nombre institución",
            "nombre_ies",
            "ies_nombre",
            "institucion_educacion_superior",
            "institución educación superior",
            "universidad",
            "ies",
            "institucion",
            "institución"
        ],
        excluir=[
            "codigo", "cod", "id",
            "sector", "oficial", "privado",
            "caracter", "carácter",
            "naturaleza", "tipo",
            "linea", "línea", "modalidad"
        ]
    )

    col_sector = seleccionar_columna_por_patrones(
        registros,
        [
            "sector",
            "naturaleza",
            "caracter",
            "carácter",
            "oficial",
            "privado"
        ],
        excluir=["codigo", "cod", "id"]
    )

    registros_filtrados = [
        registro
        for registro in registros
        if registro_coincide_territorio(
            registro=registro,
            departamento=departamento,
            municipio=municipio,
            col_departamento=col_departamento,
            col_municipio=col_municipio
        )
    ]

    registros_vigencia, anio_usado = filtrar_por_vigencia_mas_reciente(
        registros_filtrados,
        col_anio
    )

    if not es_columna_numerica_confiable(registros_vigencia, col_numero):
        col_numero = None

    total_registros_historicos = len(registros_filtrados)
    total_registros_vigencia = len(registros_vigencia)

    total_creditos = sumar_columna(
        registros=registros_vigencia,
        columna=col_numero
    )

    lineas_frecuentes = distribucion_por_columna(
        registros_vigencia,
        col_linea
    )

    instituciones_frecuentes = distribucion_por_columna(
        registros_vigencia,
        col_institucion
    )

    sectores_frecuentes = distribucion_por_columna(
        registros_vigencia,
        col_sector
    )

    muestra = construir_muestra_icetex(
        registros=registros_vigencia,
        col_departamento=col_departamento,
        col_municipio=col_municipio,
        col_anio=col_anio,
        col_numero=col_numero,
        col_linea=col_linea,
        col_institucion=col_institucion,
        col_sector=col_sector
    )

    territorio = municipio or departamento
    texto_anio = f" en la vigencia más reciente detectada ({anio_usado})" if anio_usado else ""

    if total_creditos is not None:
        respuesta_corta = (
            f"Para {territorio}, encontré una suma aproximada de {round(total_creditos):,} "
            f"créditos o beneficiarios ICETEX {etiqueta_tipo}{texto_anio}, según la columna detectada "
            "en el dataset."
        )
    else:
        respuesta_corta = (
            f"Para {territorio}, encontré {total_registros_vigencia} registros relacionados "
            f"con créditos ICETEX {etiqueta_tipo}{texto_anio}. No se identificó una columna "
            "numérica confiable para sumar créditos o beneficiarios, por lo que se reportan "
            "registros disponibles."
        )

    hallazgos = [
        f"Se filtró el dataset de créditos ICETEX {etiqueta_tipo} para {territorio}.",
        (
            f"Se usó la vigencia más reciente disponible: {anio_usado}."
            if anio_usado
            else "No se pudo detectar una columna de vigencia; se usaron los registros disponibles."
        ),
        f"Registros descargados desde datos.gov.co: {len(registros)}.",
        f"Registros históricos encontrados antes de filtrar por vigencia: {total_registros_historicos}.",
        f"Registros analizados después del filtro de vigencia: {total_registros_vigencia}.",
        (
            f"Columna usada para estimar créditos o beneficiarios: {col_numero}."
            if col_numero
            else "No se detectó una columna numérica confiable para sumar créditos o beneficiarios."
        )
    ]

    if total_creditos is not None:
        hallazgos.append(
            f"Suma aproximada de créditos o beneficiarios ICETEX {etiqueta_tipo}: {round(total_creditos):,}."
        )

    if lineas_frecuentes:
        lineas = ", ".join(
            f"{item['valor']}: {item['conteo']}"
            for item in lineas_frecuentes[:5]
        )
        hallazgos.append(f"Líneas o modalidades frecuentes: {lineas}.")

    if instituciones_frecuentes:
        instituciones = ", ".join(
            f"{item['valor']}: {item['conteo']}"
            for item in instituciones_frecuentes[:5]
        )
        hallazgos.append(f"Instituciones frecuentes en los registros: {instituciones}.")

    if sectores_frecuentes:
        sectores = ", ".join(
            f"{item['valor']}: {item['conteo']}"
            for item in sectores_frecuentes[:5]
        )
        hallazgos.append(f"Distribución frecuente por sector o naturaleza: {sectores}.")

    return {
        "tipo_consulta": f"icetex_{etiqueta_tipo}",
        "territorio_consultado": {
            "departamento": departamento,
            "municipio": municipio,
            "tipo": etiqueta_tipo
        },
        "respuesta_corta": respuesta_corta,
        "hallazgos_principales": hallazgos,
        "datos": {
            "limit_usado": limit_final,
            "q_inicial": q_inicial,
            "anio_usado": anio_usado,
            "tipo_credito": etiqueta_tipo,
            "total_registros_descargados": len(registros),
            "total_registros_historicos": total_registros_historicos,
            "total_registros_vigencia": total_registros_vigencia,
            "total_creditos_o_beneficiarios_aproximado": (
                round(total_creditos) if total_creditos is not None else None
            ),
            "lineas_o_modalidades_frecuentes": lineas_frecuentes,
            "instituciones_frecuentes": instituciones_frecuentes,
            "sectores_frecuentes": sectores_frecuentes,
            "columnas_detectadas": {
                "departamento": col_departamento,
                "municipio": col_municipio,
                "anio": col_anio,
                "creditos_o_beneficiarios": col_numero,
                "linea_o_modalidad": col_linea,
                "institucion": col_institucion,
                "sector": col_sector
            },
            "muestra_icetex": muestra
        },
        "fuentes_usadas": [fuente],
        "limitaciones": [
            "El conteo es aproximado y depende de la columna numérica detectada en el dataset.",
            "Si no se detecta una columna numérica confiable, se reporta el número de registros disponibles en la vigencia.",
            "Los registros pueden representar créditos, beneficiarios, renovaciones u otra unidad de reporte según la estructura de la fuente.",
            "Los registros históricos no equivalen necesariamente al dato actual.",
            "La lectura es descriptiva y no prueba causas sobre acceso, permanencia o financiación educativa.",
            "Para consultas departamentales se evita usar búsqueda textual inicial cuando puede sesgar la muestra; por eso se descargan más registros y se filtra localmente."
        ],
        "sugerencias_de_siguiente_pregunta": [
            f"¿Cómo se relacionan bachilleres, educación superior e ICETEX en {territorio}?",
            f"¿Qué programas de educación superior aparecen en {territorio}?",
            (
                f"¿Qué créditos ICETEX renovados aparecen en {territorio}?"
                if etiqueta_tipo == "otorgados"
                else f"¿Qué créditos ICETEX otorgados aparecen en {territorio}?"
            )
        ]
    }