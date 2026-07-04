import re
import unicodedata
from typing import Any, Dict, List, Optional

import requests

try:
    from config import DATASETS, MAX_LIMIT, DEFAULT_LIMIT
except Exception:
    DATASETS = {}
    MAX_LIMIT = 1_000_000
    DEFAULT_LIMIT = 100_000


REQUEST_TIMEOUT = 60


# ============================================================
# Normalización y validaciones
# ============================================================

def normalizar_texto(valor: Any) -> str:
    """
    Normaliza textos para comparar sin depender de tildes, mayúsculas o signos.
    Ejemplo: 'Villavicencio', 'villavicencio' y 'VILLAVICENCIO' se vuelven comparables.
    """
    if valor is None:
        return ""

    texto = str(valor).strip().lower()

    texto = "".join(
        c for c in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(c)
    )

    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    return texto


def limpiar_texto_busqueda(valor: Optional[str]) -> Optional[str]:
    """
    Limpia textos antes de enviarlos a $q.
    Devuelve None cuando el texto está vacío.
    """
    if valor is None:
        return None

    texto = str(valor).strip()

    if not texto:
        return None

    if texto.lower() in ["none", "null", "nan"]:
        return None

    return texto


def resolver_limit(limit: Optional[int], minimo: int = 1) -> int:
    """
    Asegura que el límite sea entero, no menor al mínimo y no mayor a MAX_LIMIT.
    """
    try:
        limit_final = int(limit) if limit is not None else DEFAULT_LIMIT
    except (TypeError, ValueError):
        limit_final = DEFAULT_LIMIT

    limit_final = max(minimo, limit_final)
    limit_final = min(limit_final, int(MAX_LIMIT))

    return limit_final


def validar_dataset(dataset_key: str) -> Dict[str, Any]:
    """
    Verifica que el dataset exista en config.py.
    """
    if dataset_key not in DATASETS:
        claves = list(DATASETS.keys())
        raise ValueError(
            f"No existe el dataset '{dataset_key}'. Datasets disponibles: {claves}"
        )

    dataset = DATASETS[dataset_key]

    if not dataset.get("url"):
        raise ValueError(
            f"El dataset '{dataset_key}' no tiene URL configurada."
        )

    return dataset


# ============================================================
# Consulta base a datos.gov.co / Socrata
# ============================================================

def consultar_dataset(
    dataset_key: str,
    limit: int = DEFAULT_LIMIT,
    q: Optional[str] = None,
    params_extra: Optional[Dict[str, Any]] = None,
    timeout: int = REQUEST_TIMEOUT
) -> List[Dict[str, Any]]:
    """
    Consulta un dataset de datos.gov.co usando su endpoint JSON.

    Parámetros:
    - dataset_key: clave configurada en config.py.
    - limit: cantidad máxima de registros.
    - q: búsqueda textual general soportada por Socrata.
    - params_extra: permite enviar parámetros Socrata adicionales como $select, $where, $order.
    - timeout: tiempo máximo de espera de la consulta.

    Nota:
    Para consultas departamentales grandes, algunos servicios especializados prefieren no usar $q
    y filtrar localmente, porque $q puede traer una muestra parcial.
    """
    dataset = validar_dataset(dataset_key)
    limit_final = resolver_limit(limit)

    params = {
        "$limit": limit_final
    }

    q_limpio = limpiar_texto_busqueda(q)

    if q_limpio:
        params["$q"] = q_limpio

    if params_extra:
        for clave, valor in params_extra.items():
            if valor is not None:
                params[clave] = valor

    try:
        respuesta = requests.get(
            dataset["url"],
            params=params,
            timeout=timeout
        )

    except requests.Timeout as error:
        raise RuntimeError(
            f"La consulta a datos.gov.co superó el tiempo de espera: {str(error)}"
        )

    except requests.RequestException as error:
        raise RuntimeError(
            f"No fue posible conectarse con datos.gov.co: {str(error)}"
        )

    if respuesta.status_code != 200:
        raise RuntimeError(
            f"datos.gov.co respondió con error {respuesta.status_code}: "
            f"{respuesta.text[:500]}"
        )

    try:
        datos = respuesta.json()
    except ValueError as error:
        raise RuntimeError(
            f"La respuesta de datos.gov.co no pudo interpretarse como JSON: {str(error)}"
        )

    if not isinstance(datos, list):
        raise RuntimeError(
            "La respuesta de datos.gov.co no tiene el formato esperado de lista de registros."
        )

    return datos


# ============================================================
# Exploración de columnas
# ============================================================

def explorar_columnas_dataset(
    dataset_key: str,
    limit: int = 50
) -> Dict[str, Any]:
    """
    Explora columnas de un dataset a partir de una muestra de registros.
    """
    dataset = validar_dataset(dataset_key)
    limit_final = resolver_limit(limit, minimo=1)

    registros = consultar_dataset(
        dataset_key=dataset_key,
        limit=limit_final
    )

    columnas = {}

    for registro in registros:
        for columna, valor in registro.items():
            if columna not in columnas:
                columnas[columna] = {
                    "nombre_columna": columna,
                    "ejemplos": [],
                    "posible_uso": inferir_posible_uso_columna(columna)
                }

            if valor is not None and len(columnas[columna]["ejemplos"]) < 5:
                valor_texto = str(valor)

                if valor_texto not in columnas[columna]["ejemplos"]:
                    columnas[columna]["ejemplos"].append(valor_texto)

    return {
        "dataset_key": dataset_key,
        "dataset": dataset,
        "limit_usado": limit_final,
        "registros_analizados": len(registros),
        "total_columnas_detectadas": len(columnas),
        "columnas": list(columnas.values())
    }


def inferir_posible_uso_columna(nombre_columna: str) -> str:
    """
    Da una interpretación inicial de la columna para que el GPT o la app
    puedan explicar mejor su posible significado.
    """
    nombre = normalizar_texto(nombre_columna)

    if any(palabra in nombre for palabra in ["departamento", "depto", "dpto"]):
        return "Ubicación departamental"

    if any(palabra in nombre for palabra in ["municipio", "ciudad", "mpio"]):
        return "Ubicación municipal"

    if any(palabra in nombre for palabra in [
        "institucion", "establecimiento", "sede", "colegio", "ies"
    ]):
        return "Identificación de institución, sede o establecimiento educativo"

    if any(palabra in nombre for palabra in [
        "programa", "formacion", "academico", "academica", "carrera"
    ]):
        return "Información de programa educativo"

    if any(palabra in nombre for palabra in [
        "sector", "oficial", "privado", "no oficial", "naturaleza"
    ]):
        return "Clasificación institucional o sector educativo"

    if any(palabra in nombre for palabra in [
        "anio", "ano", "vigencia", "periodo", "fecha"
    ]):
        return "Año, periodo, fecha o vigencia"

    if any(palabra in nombre for palabra in [
        "matricula", "cobertura", "desercion", "aprobacion",
        "reprobacion", "repitencia", "permanencia"
    ]):
        return "Indicador educativo"

    if any(palabra in nombre for palabra in [
        "bachiller", "egresado", "graduado", "grado 11", "aprobados"
    ]):
        return "Dato asociado a bachilleres o egresados de educación media"

    if any(palabra in nombre for palabra in [
        "credito", "creditos", "icetex", "beneficiario", "beneficiarios"
    ]):
        return "Dato asociado a financiación educativa o créditos ICETEX"

    if any(palabra in nombre for palabra in [
        "latitud", "longitud", "ubicacion", "geocoded", "coordenada"
    ]):
        return "Ubicación geográfica"

    return "Dato descriptivo o variable del dataset"


# ============================================================
# Búsqueda flexible
# ============================================================

def buscar_en_dataset(
    dataset_key: str,
    texto: Optional[str] = None,
    departamento: Optional[str] = None,
    municipio: Optional[str] = None,
    limit: int = DEFAULT_LIMIT,
    usar_q: bool = True
) -> Dict[str, Any]:
    """
    Búsqueda flexible sobre un dataset.

    La función puede hacer una búsqueda inicial en datos.gov.co usando $q
    y luego aplica filtros locales para mejorar la precisión.

    Recomendación:
    - Para consultas municipales, usar $q suele ayudar.
    - Para consultas departamentales grandes, algunos servicios especializados
      prefieren usar_q=False para evitar muestras parciales.
    """
    dataset = validar_dataset(dataset_key)
    limit_final = resolver_limit(limit)

    texto_limpio = limpiar_texto_busqueda(texto)
    departamento_limpio = limpiar_texto_busqueda(departamento)
    municipio_limpio = limpiar_texto_busqueda(municipio)

    q_inicial = None

    if usar_q:
        q_inicial = texto_limpio or municipio_limpio or departamento_limpio

    registros = consultar_dataset(
        dataset_key=dataset_key,
        limit=limit_final,
        q=q_inicial
    )

    texto_norm = normalizar_texto(texto_limpio)
    departamento_norm = normalizar_texto(departamento_limpio)
    municipio_norm = normalizar_texto(municipio_limpio)

    resultados = []

    for registro in registros:
        valores_normalizados = {
            columna: normalizar_texto(valor)
            for columna, valor in registro.items()
        }

        texto_completo = " ".join(valores_normalizados.values())

        cumple_texto = True
        cumple_departamento = True
        cumple_municipio = True

        if texto_norm:
            cumple_texto = texto_norm in texto_completo

        if departamento_norm:
            cumple_departamento = departamento_norm in texto_completo

        if municipio_norm:
            cumple_municipio = municipio_norm in texto_completo

        if cumple_texto and cumple_departamento and cumple_municipio:
            resultados.append(registro)

    return {
        "dataset_key": dataset_key,
        "dataset": dataset,
        "filtros_usados": {
            "texto": texto_limpio,
            "departamento": departamento_limpio,
            "municipio": municipio_limpio,
            "limit": limit_final,
            "usar_q": usar_q,
            "q_inicial": q_inicial
        },
        "total_registros_descargados": len(registros),
        "total_resultados": len(resultados),
        "resultados": resultados
    }


# ============================================================
# Utilidad para selección de columnas en servicios especializados
# ============================================================

def seleccionar_columna_por_patrones(
    registros: List[Dict[str, Any]],
    patrones: List[str],
    excluir: Optional[List[str]] = None
) -> Optional[str]:
    """
    Busca una columna por coincidencia exacta o parcial con patrones.
    Es útil para servicios especializados que necesitan detectar columnas
    aunque los datasets tengan nombres diferentes.

    Primero intenta coincidencia exacta normalizada.
    Luego intenta coincidencia parcial.
    """
    excluir = excluir or []

    if not registros:
        return None

    columnas = set()

    for registro in registros[:200]:
        columnas.update(registro.keys())

    patrones_norm = [normalizar_texto(p) for p in patrones]
    excluir_norm = [normalizar_texto(e) for e in excluir]

    for columna in columnas:
        nombre = normalizar_texto(columna)

        coincide = any(p == nombre for p in patrones_norm)
        excluida = any(e in nombre for e in excluir_norm)

        if coincide and not excluida:
            return columna

    for columna in columnas:
        nombre = normalizar_texto(columna)

        coincide = any(p in nombre for p in patrones_norm)
        excluida = any(e in nombre for e in excluir_norm)

        if coincide and not excluida:
            return columna

    return None