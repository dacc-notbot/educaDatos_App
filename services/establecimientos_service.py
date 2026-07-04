from collections import Counter
from typing import Any, Dict, List, Optional

from services.socrata_service import (
    consultar_dataset,
    normalizar_texto,
    seleccionar_columna_por_patrones,
)

try:
    from config import (
        DEFAULT_ANALYTIC_LIMIT,
        MAX_LIMIT,
        MIN_LIMIT_DEPARTAMENTAL,
        MIN_LIMIT_MUNICIPAL,
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


def formatear_numero(valor: Any) -> str:
    try:
        numero = int(float(valor))
        return f"{numero:,}".replace(",", ".")
    except Exception:
        return str(valor)


def resolver_limit_establecimientos(
    departamento: Optional[str],
    municipio: Optional[str],
    limit: Optional[int],
) -> int:
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


def normalizar_modo_respuesta(modo_respuesta: Optional[str]) -> str:
    """
    Modos disponibles:
    - conteo: entrega resumen numérico y NO entrega lista.
    - lista: entrega lista de colegios filtrada por vigencia reciente y sector si aplica.
    """
    modo = normalizar_texto(modo_respuesta or "conteo")

    if modo in ["lista", "detalle", "detallado", "listado", "mostrar_lista"]:
        return "lista"

    return "conteo"


def texto_completo_registro(registro: Dict[str, Any]) -> str:
    return normalizar_texto(" ".join(str(valor) for valor in registro.values()))


def registro_coincide_territorio(
    registro: Dict[str, Any],
    departamento: Optional[str],
    municipio: Optional[str],
    col_departamento: Optional[str],
    col_municipio: Optional[str],
) -> bool:
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

        if col_municipio:
            valor_municipio = normalizar_texto(registro.get(col_municipio))
            if valor_municipio != municipio_norm:
                return False
        elif municipio_norm not in texto_completo:
            return False

    return True


def filtrar_por_vigencia_mas_reciente(
    registros: List[Dict[str, Any]],
    col_anio: Optional[str],
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


def contar_unicos(
    registros: List[Dict[str, Any]],
    columna: Optional[str],
) -> Optional[int]:
    if not registros or not columna:
        return None

    valores = set()
    for registro in registros:
        valor = limpiar_valor(registro.get(columna))
        if valor:
            valores.add(normalizar_texto(valor))

    return len(valores)


def sumar_columna(
    registros: List[Dict[str, Any]],
    columna: Optional[str],
) -> Optional[int]:
    if not registros or not columna:
        return None

    total = 0
    encontro = False

    for registro in registros:
        numero = valor_a_numero(registro.get(columna))
        if numero is not None:
            total += numero
            encontro = True

    if not encontro:
        return None

    return int(total)


def distribucion_por_columna(
    registros: List[Dict[str, Any]],
    columna: Optional[str],
    top_n: Optional[int] = None,
) -> Dict[str, int]:
    if not registros or not columna:
        return {}

    contador = Counter()

    for registro in registros:
        valor = limpiar_valor(registro.get(columna)) or "SIN DATO"
        contador[valor] += 1

    if top_n:
        return dict(contador.most_common(top_n))

    return dict(contador)


def normalizar_sector_consulta(sector: Optional[str]) -> Optional[str]:
    if not sector:
        return None

    sector_norm = normalizar_texto(sector)

    if any(
        palabra in sector_norm
        for palabra in [
            "no oficial",
            "nooficial",
            "privado",
            "privados",
            "privada",
            "privadas",
            "particular",
            "particulares",
        ]
    ):
        return "NO_OFICIAL"

    if any(
        palabra in sector_norm
        for palabra in [
            "oficial",
            "oficiales",
            "publico",
            "publicos",
            "publica",
            "publicas",
        ]
    ):
        return "OFICIAL"

    return None


def registro_coincide_sector(
    registro: Dict[str, Any],
    sector: Optional[str],
    col_sector: Optional[str],
) -> bool:
    if not sector:
        return True

    if not col_sector:
        return True

    sector_consulta = normalizar_sector_consulta(sector)
    if not sector_consulta:
        return True

    valor_sector = normalizar_texto(registro.get(col_sector))

    if sector_consulta == "OFICIAL":
        return valor_sector == "oficial"

    if sector_consulta == "NO_OFICIAL":
        return valor_sector in ["no oficial", "nooficial", "privado", "privada"]

    return True


def construir_lista_establecimientos(
    registros: List[Dict[str, Any]],
    col_nombre: Optional[str],
    col_sector: Optional[str],
    col_direccion: Optional[str],
    col_matricula: Optional[str],
    col_codigo_establecimiento: Optional[str],
    max_items: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Construye una lista sin duplicados.

    Si max_items es None, devuelve todos los establecimientos únicos encontrados.
    Si max_items tiene valor, limita la lista.
    """
    lista = []
    vistos = set()

    for registro in registros:
        nombre = limpiar_valor(registro.get(col_nombre)) if col_nombre else ""
        if not nombre:
            continue

        codigo = (
            limpiar_valor(registro.get(col_codigo_establecimiento))
            if col_codigo_establecimiento
            else ""
        )
        clave = normalizar_texto(codigo or nombre)

        if clave in vistos:
            continue

        vistos.add(clave)

        item = {"nombre_establecimiento": nombre}

        if codigo:
            item["codigo_establecimiento"] = codigo

        if col_sector:
            sector = limpiar_valor(registro.get(col_sector))
            if sector:
                item["sector"] = sector

        if col_direccion:
            direccion = limpiar_valor(registro.get(col_direccion))
            if direccion:
                item["direccion"] = direccion

        if col_matricula:
            matricula = limpiar_valor(registro.get(col_matricula))
            if matricula:
                item["matricula"] = matricula

        lista.append(item)

        if max_items is not None and len(lista) >= max_items:
            break

    return lista


def construir_sugerencias_establecimientos(
    territorio: str,
    municipio: Optional[str],
    departamento: Optional[str],
    modo: str,
    sector_normalizado: Optional[str],
) -> List[str]:
    territorio_pregunta = municipio or departamento or territorio

    if modo == "conteo":
        return [
            f"Muéstrame la lista de colegios oficiales de {territorio_pregunta}",
            f"Muéstrame la lista de colegios no oficiales o privados de {territorio_pregunta}",
            f"¿Cómo se relacionan estos colegios con matrícula o permanencia en {territorio_pregunta}?",
        ]

    if sector_normalizado == "OFICIAL":
        return [
            f"¿Cuántos colegios oficiales y privados hay en {territorio_pregunta}?",
            f"Muéstrame la lista de colegios no oficiales o privados de {territorio_pregunta}",
            f"Haz un diagnóstico educativo de {territorio_pregunta}",
        ]

    if sector_normalizado == "NO_OFICIAL":
        return [
            f"¿Cuántos colegios oficiales y privados hay en {territorio_pregunta}?",
            f"Muéstrame la lista de colegios oficiales de {territorio_pregunta}",
            f"Haz un diagnóstico educativo de {territorio_pregunta}",
        ]

    return [
        f"¿Cuántos colegios oficiales y privados hay en {territorio_pregunta}?",
        f"Muéstrame la lista de colegios oficiales de {territorio_pregunta}",
        f"Muéstrame la lista de colegios no oficiales o privados de {territorio_pregunta}",
    ]


# ============================================================
# Servicio principal
# ============================================================


def consultar_establecimientos_educativos_service(
    departamento: Optional[str] = None,
    municipio: Optional[str] = None,
    sector: Optional[str] = None,
    limit: int = DEFAULT_ANALYTIC_LIMIT,
    modo_respuesta: str = "conteo",
) -> Dict[str, Any]:
    """
    Consulta establecimientos educativos.

    Modo conteo:
    - usa solo la vigencia más reciente,
    - cuenta establecimientos únicos,
    - calcula distribución oficial/no oficial,
    - NO devuelve lista detallada.

    Modo lista:
    - usa solo la vigencia más reciente,
    - filtra por sector si aplica,
    - devuelve todos los establecimientos únicos encontrados.
    """
    if not departamento and not municipio:
        raise ValueError(
            "Debes indicar al menos un departamento o municipio para consultar "
            "establecimientos educativos."
        )

    modo = normalizar_modo_respuesta(modo_respuesta)
    sector_normalizado = normalizar_sector_consulta(sector)
    limit_final = resolver_limit_establecimientos(
        departamento=departamento,
        municipio=municipio,
        limit=limit,
    )
    q_inicial = municipio if municipio else None

    registros = consultar_dataset(
        dataset_key="establecimientos_educativos",
        limit=limit_final,
        q=q_inicial,
    )

    fuente = {
        "dataset_key": "establecimientos_educativos",
        "nombre": "MEN - Establecimientos educativos de preescolar, básica y media",
        "url": "https://www.datos.gov.co/resource/cfw5-qzt5.json",
        "url_portal": "https://www.datos.gov.co",
        "descripcion": "Fuente pública del Gobierno de Colombia sobre establecimientos educativos.",
    }

    territorio = municipio or departamento

    if not registros:
        return {
            "tipo_consulta": "establecimientos_educativos",
            "modo_respuesta": modo,
            "territorio_consultado": {
                "departamento": departamento,
                "municipio": municipio,
                "sector": sector_normalizado,
            },
            "respuesta_corta": (
                f"No encontré registros de establecimientos educativos para {territorio} "
                "con los filtros usados."
            ),
            "hallazgos_principales": [
                "No se encontraron registros con los filtros utilizados.",
                "Puedes intentar con otro nombre de municipio o departamento.",
            ],
            "datos": {
                "modo_respuesta": modo,
                "limit_usado": limit_final,
                "total_registros_descargados": 0,
                "vigencia_mas_reciente": None,
                "anio_usado": None,
                "total_registros_historicos": 0,
                "total_registros_vigencia": 0,
                "total_establecimientos_unicos": 0,
                "total_sedes_reportadas": None,
                "distribucion_sector": {},
                "lista_establecimientos": [],
                "muestra_establecimientos": [],
            },
            "fuentes_usadas": [fuente],
            "limitaciones": [
                "La ausencia de resultados puede depender de la forma como aparece registrado el territorio."
            ],
            "sugerencias_de_siguiente_pregunta": [
                f"¿Cuántos colegios hay en {territorio}?",
                f"Muéstrame la lista de colegios oficiales de {territorio}",
                f"Muéstrame la lista de colegios no oficiales o privados de {territorio}",
            ],
        }

    col_departamento = seleccionar_columna_por_patrones(
        registros,
        ["departamento", "nombre_departamento", "nom_departamento"],
        excluir=["codigo", "cod", "id"],
    )
    col_municipio = seleccionar_columna_por_patrones(
        registros,
        ["municipio", "nombre_municipio", "nom_municipio"],
        excluir=["codigo", "cod", "id"],
    )
    col_anio = seleccionar_columna_por_patrones(
        registros,
        ["a_o", "ano", "anio", "año", "vigencia", "periodo"],
        excluir=["codigo", "cod", "id"],
    )
    col_codigo_establecimiento = seleccionar_columna_por_patrones(
        registros,
        [
            "codigo_dane",
            "cod_dane_establecimiento",
            "codigo_dane_establecimiento",
            "cod_establecimiento",
            "codigo_establecimiento",
            "codigo_dane_sede",
        ],
        excluir=[],
    )
    col_nombre = seleccionar_columna_por_patrones(
        registros,
        [
            "nombre_establecimiento",
            "nombreestablecimiento",
            "establecimiento",
            "institucion_educativa",
            "institución educativa",
            "institucion",
            "institución",
            "nombre",
        ],
        excluir=["codigo", "cod", "id", "sede"],
    )
    col_sector = seleccionar_columna_por_patrones(
        registros,
        ["sector", "nombre_sector", "sector_educativo"],
        excluir=["codigo", "cod", "id"],
    )
    col_direccion = seleccionar_columna_por_patrones(
        registros,
        ["direccion", "dirección", "dir"],
        excluir=["codigo", "cod", "id"],
    )
    col_matricula = seleccionar_columna_por_patrones(
        registros,
        ["total_matricula", "matricula_total", "matricula", "matrícula"],
        excluir=["codigo", "cod", "id"],
    )
    col_sedes = seleccionar_columna_por_patrones(
        registros,
        ["cantidad_sedes", "numero_sedes", "número_sedes", "total_sedes", "sedes"],
        excluir=["codigo", "cod", "id"],
    )

    # 1. Primero filtrar solo por territorio.
    registros_territorio = [
        registro
        for registro in registros
        if registro_coincide_territorio(
            registro=registro,
            departamento=departamento,
            municipio=municipio,
            col_departamento=col_departamento,
            col_municipio=col_municipio,
        )
    ]

    # 2. Detectar vigencia más reciente usando todo el territorio.
    registros_vigencia_territorio, anio_usado = filtrar_por_vigencia_mas_reciente(
        registros_territorio,
        col_anio,
    )

    # 3. Calcular distribución por sector en la vigencia más reciente, sin filtrar por sector.
    distribucion_sector_general = distribucion_por_columna(
        registros_vigencia_territorio,
        col_sector,
    )
    total_general_vigencia = len(registros_vigencia_territorio)
    total_general_unicos = (
        contar_unicos(registros_vigencia_territorio, col_codigo_establecimiento)
        or contar_unicos(registros_vigencia_territorio, col_nombre)
        or total_general_vigencia
    )

    # 4. Luego aplicar sector solo si el usuario pidió lista o filtro específico.
    registros_vigencia = [
        registro
        for registro in registros_vigencia_territorio
        if registro_coincide_sector(
            registro=registro,
            sector=sector_normalizado,
            col_sector=col_sector,
        )
    ]

    total_registros_historicos = len(registros_territorio)
    total_registros_vigencia = len(registros_vigencia)
    total_establecimientos_unicos = (
        contar_unicos(registros_vigencia, col_codigo_establecimiento)
        or contar_unicos(registros_vigencia, col_nombre)
        or total_registros_vigencia
    )
    total_sedes_reportadas = sumar_columna(registros_vigencia, col_sedes)

    if modo == "lista":
        lista_establecimientos = construir_lista_establecimientos(
            registros=registros_vigencia,
            col_nombre=col_nombre,
            col_sector=col_sector,
            col_direccion=col_direccion,
            col_matricula=col_matricula,
            col_codigo_establecimiento=col_codigo_establecimiento,
            max_items=None,
        )
    else:
        lista_establecimientos = []

    texto_anio = f" al año {anio_usado}" if anio_usado else ""

    if modo == "conteo":
        oficiales = distribucion_sector_general.get("OFICIAL")
        no_oficiales = (
            distribucion_sector_general.get("NO_OFICIAL")
            or distribucion_sector_general.get("NO OFICIAL")
            or distribucion_sector_general.get("No oficial")
        )

        if oficiales is not None and no_oficiales is not None:
            respuesta_corta = (
                f"Según los datos más recientes disponibles{texto_anio}, en {territorio} "
                f"se encuentran registrados {formatear_numero(total_general_unicos)} "
                "establecimientos educativos: "
                f"{formatear_numero(oficiales)} oficiales o públicos y "
                f"{formatear_numero(no_oficiales)} no oficiales o privados."
            )
        else:
            respuesta_corta = (
                f"Según los datos más recientes disponibles{texto_anio}, en {territorio} "
                f"se encuentran registrados {formatear_numero(total_general_unicos)} "
                "establecimientos educativos."
            )

        hallazgos = [
            (
                f"La información corresponde a la vigencia más reciente disponible: {anio_usado}."
                if anio_usado
                else "No se identificó una columna de vigencia; se usaron los registros disponibles."
            ),
            "El conteo se calcula sobre establecimientos educativos únicos.",
        ]

        if oficiales is not None:
            hallazgos.append(
                f"Establecimientos oficiales o públicos: {formatear_numero(oficiales)}."
            )

        if no_oficiales is not None:
            hallazgos.append(
                f"Establecimientos no oficiales o privados: {formatear_numero(no_oficiales)}."
            )
    else:
        sector_texto = ""
        if sector_normalizado == "OFICIAL":
            sector_texto = " oficiales o públicos"
        elif sector_normalizado == "NO_OFICIAL":
            sector_texto = " no oficiales o privados"

        respuesta_corta = (
            f"Según los datos más recientes disponibles{texto_anio}, encontré "
            f"{formatear_numero(total_establecimientos_unicos)} "
            f"establecimientos educativos{sector_texto} en {territorio}. "
            "A continuación se presenta la lista registrada en la fuente consultada."
        )

        hallazgos = [
            (
                f"La lista corresponde únicamente a la vigencia más reciente disponible: {anio_usado}."
                if anio_usado
                else "No se identificó una columna de vigencia; se usaron los registros disponibles."
            ),
            f"Se encontraron {formatear_numero(total_establecimientos_unicos)} "
            f"establecimientos educativos{sector_texto}.",
        ]

        if not sector_normalizado:
            hallazgos.append(
                "La lista incluye establecimientos oficiales y no oficiales porque no se pidió un sector específico."
            )

    if modo == "conteo":
        pregunta_continuacion = (
            "¿Deseas ver la lista de colegios oficiales o la lista de colegios no oficiales/privados?"
        )
        hallazgos.append(pregunta_continuacion)

    return {
        "tipo_consulta": "establecimientos_educativos",
        "modo_respuesta": modo,
        "territorio_consultado": {
            "departamento": departamento,
            "municipio": municipio,
            "sector": sector_normalizado,
        },
        "respuesta_corta": respuesta_corta,
        "hallazgos_principales": hallazgos,
        "datos": {
            "modo_respuesta": modo,
            "limit_usado": limit_final,
            "q_inicial": q_inicial,
            "total_registros_descargados": len(registros),
            "vigencia_mas_reciente": anio_usado,
            "anio_usado": anio_usado,
            "total_registros_historicos": total_registros_historicos,
            "total_registros_vigencia": total_registros_vigencia,
            "total_establecimientos_unicos": (
                total_general_unicos
                if modo == "conteo" and not sector_normalizado
                else total_establecimientos_unicos
            ),
            "total_establecimientos_unicos_general": total_general_unicos,
            "total_sedes_reportadas": total_sedes_reportadas,
            "distribucion_sector": distribucion_sector_general,
            "sector_consultado": sector_normalizado,
            "lista_establecimientos": lista_establecimientos,
            "muestra_establecimientos": lista_establecimientos,
            "columnas_detectadas": {
                "departamento": col_departamento,
                "municipio": col_municipio,
                "anio": col_anio,
                "codigo_establecimiento": col_codigo_establecimiento,
                "nombre_establecimiento": col_nombre,
                "sector": col_sector,
                "direccion": col_direccion,
                "matricula": col_matricula,
                "sedes": col_sedes,
            },
        },
        "fuentes_usadas": [fuente],
        "limitaciones": [
            "El conteo corresponde a establecimientos educativos únicos identificados en la fuente consultada.",
            "La consulta usa la vigencia más reciente disponible; no mezcla años anteriores salvo que se solicite un comparativo histórico.",
            "Para decisiones oficiales se recomienda verificar con la Secretaría de Educación o el MEN.",
            "Si un establecimiento aparece repetido por sede, jornada u otra desagregación, el conteo único puede variar según la columna usada.",
        ],
        "sugerencias_de_siguiente_pregunta": construir_sugerencias_establecimientos(
            territorio=territorio or "el territorio consultado",
            municipio=municipio,
            departamento=departamento,
            modo=modo,
            sector_normalizado=sector_normalizado,
        ),
    }