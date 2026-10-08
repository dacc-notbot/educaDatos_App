"""Catálogo completo de la última vigencia territorial publicada por el MEN.

La agregación ocurre en la fuente: no depende de una muestra de registros
educativos ni mezcla nombres de municipios correspondientes a distintos años.
"""

from collections import defaultdict
from typing import Any

from config import DATASETS
from services.socrata_service import consultar_dataset
from utils.normalizacion import normalizar_texto

DATASET_TERRITORIAL = "estadisticas_municipio"
TAMANO_PAGINA = 500
MAX_MUNICIPIOS = 10_000


def _consulta(params: dict[str, Any], limit: int = TAMANO_PAGINA):
    return consultar_dataset(
        DATASET_TERRITORIAL, limit=limit, params_extra=params,
    )


def _entero(valor: Any) -> int:
    try:
        numero = int(str(valor))
    except (TypeError, ValueError) as error:
        raise RuntimeError("No pudimos verificar el catálogo de municipios.") from error
    if numero < 1:
        raise RuntimeError("La fuente oficial no publicó un catálogo territorial completo.")
    return numero


def consultar_catalogo_territorios() -> dict[str, Any]:
    # consultar_dataset usa HTTPS con verificación TLS y la caché con TTL,
    # bloqueo por consulta y escritura atómica compartida con las demás fuentes.
    vigencias = _consulta({"$select": "max(a_o) as anio"}, limit=1)
    if len(vigencias) != 1 or not isinstance(vigencias[0], dict):
        raise RuntimeError("No pudimos identificar el año del catálogo territorial.")
    anio = _entero(vigencias[0].get("anio"))
    if not 1900 <= anio <= 9999:
        raise RuntimeError("El catálogo territorial no informa un año válido.")
    filtro = f"a_o='{anio}'"
    resumen = _consulta({
        "$select": "count(distinct c_digo_municipio) as municipios,count(distinct departamento) as departamentos",
        "$where": filtro,
    }, limit=1)
    if len(resumen) != 1 or not isinstance(resumen[0], dict):
        raise RuntimeError("No pudimos verificar todos los municipios del catálogo.")
    total = _entero(resumen[0].get("municipios"))
    departamentos_esperados = _entero(resumen[0].get("departamentos"))
    if total > MAX_MUNICIPIOS:
        raise RuntimeError("El catálogo territorial supera el tamaño que podemos verificar.")

    filas: list[dict[str, Any]] = []
    offset = 0
    while True:
        pagina = _consulta({
            "$select": "departamento,municipio,c_digo_municipio",
            "$group": "departamento,municipio,c_digo_municipio",
            "$where": filtro,
            "$order": "departamento,municipio,c_digo_municipio",
            "$offset": offset,
        }, limit=TAMANO_PAGINA)
        if not isinstance(pagina, list) or any(not isinstance(fila, dict) for fila in pagina):
            raise RuntimeError("La fuente oficial devolvió municipios que no pudimos leer.")
        filas.extend(pagina)
        if len(filas) > total or len(pagina) > TAMANO_PAGINA:
            raise RuntimeError("La fuente informa relaciones territoriales inconsistentes.")
        if len(pagina) < TAMANO_PAGINA:
            break
        offset += TAMANO_PAGINA
    if len(filas) != total:
        raise RuntimeError("La fuente no devolvió todos los municipios; vuelve a intentarlo.")

    grupos: dict[str, list[dict[str, str]]] = defaultdict(list)
    codigos: set[str] = set()
    pares: set[tuple[str, str]] = set()
    for fila in filas:
        departamento = str(fila.get("departamento") or "").strip()
        municipio = str(fila.get("municipio") or "").strip()
        codigo = str(fila.get("c_digo_municipio") or "").strip()
        if not departamento or not municipio or not codigo.isdigit() or not 1 <= len(codigo) <= 5:
            raise RuntimeError("La fuente no informa la ubicación de todos los municipios.")
        codigo = codigo.zfill(5)
        par = (normalizar_texto(departamento), normalizar_texto(municipio))
        if codigo in codigos or par in pares:
            raise RuntimeError("La fuente informa municipios repetidos o ubicaciones inconsistentes.")
        codigos.add(codigo)
        pares.add(par)
        grupos[departamento].append({"municipio": municipio, "codigo": codigo})
    if len(grupos) != departamentos_esperados:
        raise RuntimeError("La fuente no devolvió todos los departamentos del catálogo.")

    return {
        "departamentos": [
            {"departamento": departamento, "municipios": sorted(grupos[departamento], key=lambda m: normalizar_texto(m["municipio"]))}
            for departamento in sorted(grupos, key=normalizar_texto)
        ],
        "fuente": DATASETS[DATASET_TERRITORIAL]["nombre"],
        "anio": anio,
    }
