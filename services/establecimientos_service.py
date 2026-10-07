from utils.normalizacion import valor_a_numero
from decimal import Decimal, InvalidOperation
from collections import Counter

from config import DATASETS
from services.directorio_colegios import consultar_directorio_vigente
from typing import Any, Dict, List, Optional

from services.socrata_service import (
    normalizar_texto,
)

from config import (
    DEFAULT_ANALYTIC_LIMIT,
    MAX_LIMIT,
    MIN_LIMIT_DEPARTAMENTAL,
    MIN_LIMIT_MUNICIPAL,
)


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
    texto_completo = None

    if departamento:
        departamento_norm = normalizar_texto(departamento)

        if col_departamento:
            valor_departamento = normalizar_texto(registro.get(col_departamento))
            if valor_departamento != departamento_norm:
                return False
        else:
            if texto_completo is None:
                texto_completo = texto_completo_registro(registro)
            if departamento_norm not in texto_completo:
                return False

    if municipio:
        municipio_norm = normalizar_texto(municipio)

        if col_municipio:
            valor_municipio = normalizar_texto(registro.get(col_municipio))
            if valor_municipio != municipio_norm:
                return False
        else:
            if texto_completo is None:
                texto_completo = texto_completo_registro(registro)
            if municipio_norm not in texto_completo:
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
    """Una entrada por código DANE; nombres normalizados si falta el código."""
    unicos = {}
    for registro in registros:
        nombre = limpiar_valor(registro.get(col_nombre)) if col_nombre else ""
        codigo = (
            limpiar_valor(registro.get(col_codigo_establecimiento))
            if col_codigo_establecimiento
            else ""
        )
        if codigo:
            try:
                numero = Decimal(codigo)
                if numero.is_finite() and numero == numero.to_integral_value():
                    codigo = str(int(numero))
            except InvalidOperation:
                pass
        if not codigo and not nombre:
            raise RuntimeError(
                "La fuente contiene colegios sin código ni nombre. No es posible confirmar un conteo único."
            )
        sector = (
            normalizar_sector_consulta(registro.get(col_sector)) if col_sector else None
        )
        tipo = {"OFICIAL": "Público", "NO_OFICIAL": "Privado"}.get(sector, "Sin dato")
        clave = (
            ("codigo", codigo)
            if codigo
            else (
                "nombre",
                normalizar_texto(registro.get("departamento")),
                normalizar_texto(registro.get("municipio")),
                normalizar_texto(nombre),
            )
        )
        item = {
            "nombre_establecimiento": nombre or "Nombre no informado",
            "codigo_establecimiento": codigo,
            "sector": sector,
            "tipo": tipo,
        }
        if clave in unicos:
            anterior = unicos[clave]
            if anterior["nombre_establecimiento"] == "Nombre no informado" and nombre:
                anterior["nombre_establecimiento"] = nombre
            if anterior["tipo"] != tipo:
                anterior["tipo"] = "Sin dato"
                anterior["sector"] = None
                anterior["sector_inconsistente"] = True
        else:
            unicos[clave] = item
    lista = sorted(
        unicos.values(),
        key=lambda item: (
            normalizar_texto(item["nombre_establecimiento"]),
            item["codigo_establecimiento"],
        ),
    )
    return lista if max_items is None else lista[:max_items]


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
# Servicio principal: una misma lista única para conteos y filtros.
# ============================================================


def consultar_establecimientos_educativos_service(
    departamento: Optional[str] = None,
    municipio: Optional[str] = None,
    sector: Optional[str] = None,
    limit: int = DEFAULT_ANALYTIC_LIMIT,
    modo_respuesta: str = "conteo",
) -> Dict[str, Any]:
    if not departamento and not municipio:
        raise ValueError(
            "Debes indicar al menos un departamento o municipio para consultar colegios."
        )
    modo = normalizar_modo_respuesta(modo_respuesta)
    sector_normalizado = normalizar_sector_consulta(sector)
    registros, anio = consultar_directorio_vigente(departamento, municipio)
    todos = construir_lista_establecimientos(
        registros, "nombre_establecimiento", "sector", None, None, "codigo_dane"
    )
    seleccionados = [
        item
        for item in todos
        if not sector_normalizado or item["sector"] == sector_normalizado
    ]
    distribucion = dict(Counter(item["sector"] or "SIN DATO" for item in todos))
    publicos = distribucion.get("OFICIAL", 0)
    privados = distribucion.get("NO_OFICIAL", 0)
    territorio = municipio or departamento
    total = len(seleccionados)
    tipo = {"OFICIAL": " público", "NO_OFICIAL": " privado"}.get(sector_normalizado, "")
    nombre = "colegio" if total == 1 else "colegios"
    if total != 1 and tipo:
        tipo += "s"
    participio = "registrado" if total == 1 else "registrados"
    respuesta = f"En {territorio} hay {formatear_numero(total)} {nombre}{tipo} {participio} en la fuente del MEN para {anio}."
    if not sector_normalizado and todos:
        respuesta += f" {formatear_numero(publicos)} públicos y {formatear_numero(privados)} privados."
    if not todos:
        respuesta = f"No se encontraron colegios registrados en {territorio} para {anio}, el año más reciente publicado por el MEN."
    limitaciones = [
        f"Información del MEN correspondiente a {anio}, el año más reciente publicado en esta fuente; no confirma cambios posteriores."
    ]
    if distribucion.get("SIN DATO"):
        limitaciones.append(
            f"{distribucion['SIN DATO']} colegios no tienen un tipo público o privado confirmado en la fuente."
        )
    if any(item.get("sector_inconsistente") for item in todos):
        limitaciones.append(
            "La fuente asigna sectores diferentes al mismo código DANE. Esos colegios aparecen con tipo «Sin dato»."
        )
    if any(not item["codigo_establecimiento"] for item in todos):
        limitaciones.append(
            "Algunos colegios no tienen código DANE; para evitar repeticiones se usa su nombre y territorio."
        )
    if any(item["nombre_establecimiento"] == "Nombre no informado" for item in todos):
        limitaciones.append(
            "Algunos colegios tienen código DANE pero no un nombre informado por la fuente."
        )
    fuente = {
        "dataset_key": "establecimientos_educativos",
        **DATASETS["establecimientos_educativos"],
        "url_portal": "https://www.datos.gov.co",
    }
    lista = seleccionados if modo == "lista" else []
    return {
        "tipo_consulta": "establecimientos_educativos",
        "modo_respuesta": modo,
        "territorio_consultado": {
            "departamento": departamento,
            "municipio": municipio,
            "sector": sector_normalizado,
        },
        "respuesta_corta": respuesta,
        "hallazgos_principales": [],
        "datos": {
            "modo_respuesta": modo,
            "territorio": {"departamento": departamento, "municipio": municipio},
            "limit_solicitado": limit,
            "limit_usado": len(registros),
            "consulta_completa": True,
            "total_registros_descargados": len(registros),
            "vigencia_mas_reciente": anio,
            "anio_usado": anio,
            "total_registros_vigencia": len(registros),
            "total_establecimientos_unicos": total,
            "total_establecimientos_unicos_general": len(todos),
            "total_sedes_reportadas": sumar_columna(registros, "cantidad_sedes"),
            "distribucion_sector": distribucion,
            "sector_consultado": sector_normalizado,
            "lista_establecimientos": lista,
            "muestra_establecimientos": lista,
            "columnas_detectadas": {
                "departamento": "departamento",
                "municipio": "municipio",
                "anio": "a_o",
                "codigo_establecimiento": "codigo_dane",
                "nombre_establecimiento": "nombre_establecimiento",
                "sector": "sector",
            },
        },
        "fuentes_usadas": [fuente],
        "limitaciones": limitaciones,
        "sugerencias_de_siguiente_pregunta": construir_sugerencias_establecimientos(
            territorio, municipio, departamento, modo, sector_normalizado
        ),
    }
