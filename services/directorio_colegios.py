"""Consulta completa del directorio del MEN para su última vigencia publicada."""

from typing import Any, Dict, List, Optional

from config import MAX_LIMIT
from services.socrata_service import consultar_dataset
from utils.normalizacion import normalizar_texto, valor_a_numero

DATASET = "establecimientos_educativos"
TAMANO_PAGINA = 5000


def literal_soql(texto: str) -> str:
    # Los nombres son valores, nunca identificadores o instrucciones SoQL.
    return "'" + texto.strip().upper().replace("'", "''") + "'"


def consultar_directorio_vigente(
    departamento: Optional[str],
    municipio: Optional[str],
    nombre: Optional[str] = None,
    codigo: Optional[str] = None,
) -> tuple[List[Dict[str, Any]], Optional[int]]:
    if codigo and (not codigo.isdigit() or not 1 <= len(codigo) <= 15):
        raise ValueError(
            "El código DANE debe contener únicamente números, hasta 15 dígitos."
        )
    if nombre and len(normalizar_texto(nombre)) < 2:
        raise ValueError(
            "Escribe al menos dos letras o números del nombre del colegio."
        )
    vigente = consultar_dataset(
        DATASET, limit=1, params_extra={"$select": "max(a_o) as vigencia"}
    )
    numero = valor_a_numero(vigente[0].get("vigencia")) if vigente else None
    if numero is None or numero != int(numero) or not 1000 <= numero <= 9999:
        raise RuntimeError(
            "La fuente de colegios no informa una vigencia válida. No es posible confirmar el directorio más reciente."
        )
    anio = int(numero)
    condiciones = [f"a_o = {anio}"]
    if departamento:
        condiciones.append(f"upper(departamento) = {literal_soql(departamento)}")
    if municipio:
        condiciones.append(f"upper(municipio) = {literal_soql(municipio)}")
    if codigo:
        condiciones.append(f"codigo_dane = {int(codigo)}")
    if nombre:
        columna = "upper(nombre_establecimiento)"
        for original, simple in zip("ÁÉÍÓÚÜÑ", "AEIOUUN"):
            columna = f"replace({columna}, '{original}', '{simple}')"
        for palabra in normalizar_texto(nombre).split():
            condiciones.append(f"contains({columna}, {literal_soql(palabra)})")
    where = " AND ".join(condiciones)
    conteo = consultar_dataset(
        DATASET, limit=1, params_extra={"$select": "count(*) as total", "$where": where}
    )
    total = valor_a_numero(conteo[0].get("total")) if conteo else None
    if total is None or total < 0 or total != int(total):
        raise RuntimeError(
            "La fuente de colegios no permitió comprobar la cantidad de registros del territorio."
        )
    if total > MAX_LIMIT:
        raise RuntimeError(
            "El directorio supera la capacidad de consulta. Consulta un municipio para obtener una lista completa."
        )
    registros = []
    while len(registros) < int(total):
        cantidad = min(TAMANO_PAGINA, int(total) - len(registros))
        pagina = consultar_dataset(
            DATASET,
            limit=cantidad,
            params_extra={
                "$where": where,
                "$order": ":id",
                "$offset": len(registros),
                "$select": "a_o,departamento,municipio,codigo_dane,nombre_establecimiento,sector,cantidad_sedes",
            },
        )
        if (
            not pagina
            or len(pagina) > cantidad
            or any(valor_a_numero(r.get("a_o")) != anio for r in pagina)
        ):
            raise RuntimeError(
                "La fuente no devolvió un directorio completo de la vigencia solicitada. Inténtalo nuevamente más tarde."
            )
        registros.extend(pagina)
    return registros, anio
