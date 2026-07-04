from typing import Any, Dict, List, Optional, Tuple

from services.socrata_service import consultar_dataset, normalizar_texto
from config import DATASET_BASE, DEFAULT_LIMIT


CACHE_TERRITORIOS = {
    "catalogo": None
}


def _buscar_columna_por_patrones(
    registros: List[Dict[str, Any]],
    patrones: List[str],
    excluir: Optional[List[str]] = None
) -> Optional[str]:
    """
    Busca columnas por patrones flexibles.
    Sirve para encontrar departamento y municipio aunque el dataset use nombres distintos.
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


def construir_catalogo_territorial(limit: int = DEFAULT_LIMIT) -> Dict[str, Any]:
    """
    Construye un catálogo nacional de departamentos y municipios desde el dataset base.
    Usa caché para evitar consultar y procesar el dataset en cada pregunta.
    """
    if CACHE_TERRITORIOS["catalogo"] is not None:
        return CACHE_TERRITORIOS["catalogo"]

    registros = consultar_dataset(
        dataset_key=DATASET_BASE,
        limit=limit
    )

    if not registros:
        catalogo_vacio = {
            "departamentos": [],
            "municipios": [],
            "pares": [],
            "columnas_detectadas": {
                "departamento": None,
                "municipio": None
            },
            "total_departamentos": 0,
            "total_municipios": 0,
            "total_pares": 0
        }

        CACHE_TERRITORIOS["catalogo"] = catalogo_vacio
        return catalogo_vacio

    col_departamento = _buscar_columna_por_patrones(
        registros,
        ["departamento", "depto", "dpto", "nombre_departamento", "nom_departamento"],
        excluir=["codigo", "cod", "id"]
    )

    col_municipio = _buscar_columna_por_patrones(
        registros,
        ["municipio", "mpio", "muni", "nombre_municipio", "nom_municipio"],
        excluir=["codigo", "cod", "id"]
    )

    departamentos = {}
    municipios = {}
    pares = []
    pares_vistos = set()

    for registro in registros:
        departamento = registro.get(col_departamento) if col_departamento else None
        municipio = registro.get(col_municipio) if col_municipio else None

        if departamento:
            dep_limpio = str(departamento).strip()
            dep_norm = normalizar_texto(dep_limpio)

            if dep_norm and dep_norm not in departamentos:
                departamentos[dep_norm] = dep_limpio

        if municipio:
            mun_limpio = str(municipio).strip()
            mun_norm = normalizar_texto(mun_limpio)

            if mun_norm and mun_norm not in municipios:
                municipios[mun_norm] = mun_limpio

        if departamento and municipio:
            dep_limpio = str(departamento).strip()
            mun_limpio = str(municipio).strip()

            par_norm = (
                normalizar_texto(dep_limpio),
                normalizar_texto(mun_limpio)
            )

            if par_norm not in pares_vistos:
                pares_vistos.add(par_norm)
                pares.append({
                    "departamento": dep_limpio,
                    "municipio": mun_limpio
                })

    catalogo = {
        "departamentos": sorted(departamentos.values()),
        "municipios": sorted(municipios.values()),
        "pares": pares,
        "columnas_detectadas": {
            "departamento": col_departamento,
            "municipio": col_municipio
        },
        "total_departamentos": len(departamentos),
        "total_municipios": len(municipios),
        "total_pares": len(pares)
    }

    CACHE_TERRITORIOS["catalogo"] = catalogo

    return catalogo


def contiene_frase_completa(texto_normalizado: str, frase_normalizada: str) -> bool:
    """
    Verifica si una frase territorial aparece como unidad completa.
    Evita falsos positivos como:
    - Achí dentro de bachilleres.
    - Cali dentro de calificaciones.
    """
    if not texto_normalizado or not frase_normalizada:
        return False

    texto_bordeado = f" {texto_normalizado} "
    frase_bordeada = f" {frase_normalizada} "

    return frase_bordeada in texto_bordeado


def par_departamento_municipio_existe(
    catalogo: Dict[str, Any],
    departamento: str,
    municipio: str
) -> bool:
    """
    Verifica si el municipio detectado pertenece al departamento detectado.
    """
    dep_norm = normalizar_texto(departamento)
    mun_norm = normalizar_texto(municipio)

    for par in catalogo.get("pares", []):
        if (
            normalizar_texto(par.get("departamento")) == dep_norm
            and normalizar_texto(par.get("municipio")) == mun_norm
        ):
            return True

    return False


def detectar_territorio_nacional(
    pregunta: str,
    limit: int = DEFAULT_LIMIT
) -> Tuple[Optional[str], Optional[str]]:
    """
    Detecta departamento y municipio en una pregunta ciudadana usando catálogo nacional.

    Correcciones clave:
    - Evita detectar municipios como subcadenas dentro de otras palabras.
      Ejemplo: Achí dentro de bachilleres.
    - Si detecta departamento y municipio, valida que el municipio pertenezca
      al departamento detectado.
    """
    texto = normalizar_texto(pregunta)
    # Caso especial: Bogotá suele aparecer en datos abiertos como Bogotá, D.C.
    # Se fuerza la detección porque es una consulta ciudadana muy frecuente.
    if contiene_frase_completa(texto, "bogota"):
        return "Bogotá, D.C.", "Bogotá, D.C."
    catalogo = construir_catalogo_territorial(limit=limit)

    departamento_detectado = None
    municipio_detectado = None

    departamentos_ordenados = sorted(
        catalogo.get("departamentos", []),
        key=lambda x: len(str(x)),
        reverse=True
    )

    for departamento in departamentos_ordenados:
        departamento_norm = normalizar_texto(departamento)

        if contiene_frase_completa(texto, departamento_norm):
            departamento_detectado = departamento
            break

    municipios_ordenados = sorted(
        catalogo.get("municipios", []),
        key=lambda x: len(str(x)),
        reverse=True
    )

    for municipio in municipios_ordenados:
        municipio_norm = normalizar_texto(municipio)

        if contiene_frase_completa(texto, municipio_norm):
            municipio_detectado = municipio
            break

    if departamento_detectado and municipio_detectado:
        pertenece = par_departamento_municipio_existe(
            catalogo=catalogo,
            departamento=departamento_detectado,
            municipio=municipio_detectado
        )

        if not pertenece:
            municipio_detectado = None

    if municipio_detectado and not departamento_detectado:
        municipio_norm = normalizar_texto(municipio_detectado)

        coincidencias = [
            par
            for par in catalogo.get("pares", [])
            if normalizar_texto(par.get("municipio")) == municipio_norm
        ]

        departamentos_posibles = sorted({
            par.get("departamento")
            for par in coincidencias
            if par.get("departamento")
        })

        if len(departamentos_posibles) == 1:
            departamento_detectado = departamentos_posibles[0]

    return departamento_detectado, municipio_detectado


def buscar_territorios_por_texto(
    texto: str,
    limit: int = DEFAULT_LIMIT,
    max_resultados: int = 20
) -> Dict[str, Any]:
    """
    Permite buscar municipios o departamentos parecidos para pruebas o autocompletado.
    """
    texto_norm = normalizar_texto(texto)
    catalogo = construir_catalogo_territorial(limit=limit)

    resultados = []

    for par in catalogo.get("pares", []):
        departamento = par.get("departamento")
        municipio = par.get("municipio")

        combinado = normalizar_texto(f"{municipio} {departamento}")

        if texto_norm in combinado:
            resultados.append(par)

        if len(resultados) >= max_resultados:
            break

    return {
        "texto_buscado": texto,
        "total_resultados": len(resultados),
        "resultados": resultados,
        "columnas_detectadas": catalogo.get("columnas_detectadas")
    }


def limpiar_cache_territorios() -> Dict[str, str]:
    """
    Permite reiniciar el catálogo territorial si se requiere reconstruirlo.
    """
    CACHE_TERRITORIOS["catalogo"] = None

    return {
        "status": "ok",
        "message": "Caché territorial limpiado correctamente."
    }