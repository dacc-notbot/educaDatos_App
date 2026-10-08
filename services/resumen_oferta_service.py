"""Resúmenes ciudadanos sobre las mismas ofertas que aparecen en el listado."""

from collections import defaultdict

from utils.normalizacion import normalizar_texto


SIN_INFORMACION = "Sin información"


def valor_publicado(valor):
    texto = str(valor).strip() if valor is not None else ""
    if normalizar_texto(texto) in {"", "na", "n a", "none", "null", "nan", "sin dato"}:
        return SIN_INFORMACION
    return texto


def estado_publicado(valor):
    texto = valor_publicado(valor)
    normalizado = normalizar_texto(texto)
    if normalizado == "activo":
        return "Activo"
    if normalizado in {"inactivo", "no activo"}:
        return "Inactivo"
    # No convierte estados desconocidos en activos o inactivos.
    return texto


def ciclo_publicado(valor, nivel):
    texto = valor_publicado(valor)
    if texto != SIN_INFORMACION:
        return texto
    normalizado = normalizar_texto(nivel)
    if normalizado in {
        "universitaria", "tecnologica", "formacion tecnica profesional",
        "tecnica profesional", "pregrado",
    }:
        return "Pregrado"
    if normalizado.startswith("especializacion") or normalizado in {
        "maestria", "doctorado", "posgrado",
    }:
        return "Posgrado"
    return SIN_INFORMACION


def totales_estado(filas):
    activos = sum(estado_publicado(fila.get("estado")) == "Activo" for fila in filas)
    inactivos = sum(estado_publicado(fila.get("estado")) == "Inactivo" for fila in filas)
    return {
        "total": len(filas),
        "activos": activos,
        "inactivos": inactivos,
        "sin_estado": len(filas) - activos - inactivos,
    }


def agrupar(filas, campo, nombre_campo=None):
    grupos = defaultdict(list)
    etiquetas = {}
    for fila in filas:
        valor = valor_publicado(fila.get(campo))
        clave = normalizar_texto(valor)
        etiquetas.setdefault(clave, valor)
        grupos[clave].append(fila)
    return sorted(
        [
            {nombre_campo or campo: etiquetas[clave], **totales_estado(grupo)}
            for clave, grupo in grupos.items()
        ],
        key=lambda grupo: (-grupo["total"], normalizar_texto(grupo[nombre_campo or campo])),
    )


def construir_resumen_oferta(lista_oferta):
    """Cuenta ofertas publicadas, nunca convierte títulos en programas únicos."""
    estados = agrupar(lista_oferta, "estado")
    grupos_institucion = defaultdict(list)
    etiquetas = {}
    for fila in lista_oferta:
        institucion = valor_publicado(fila.get("institucion"))
        clave = normalizar_texto(institucion)
        etiquetas.setdefault(clave, institucion)
        grupos_institucion[clave].append(fila)
    instituciones = []
    for clave, filas in grupos_institucion.items():
        total = totales_estado(filas)
        instituciones.append({
            "institucion": etiquetas[clave],
            "total_ofertas": total.pop("total"),
            **total,
            "modalidades": agrupar(filas, "modalidad"),
            "niveles": agrupar(filas, "nivel"),
            "ciclos": agrupar(filas, "ciclo"),
        })
    instituciones.sort(key=lambda fila: (-fila["total_ofertas"], normalizar_texto(fila["institucion"])))
    return {
        "unidad_conteo": "ofertas publicadas",
        "total_ofertas": len(lista_oferta),
        "por_estado": [{"estado": fila["estado"], "total": fila["total"]} for fila in estados],
        "por_nivel": agrupar(lista_oferta, "nivel"),
        "por_modalidad": agrupar(lista_oferta, "modalidad"),
        "por_ciclo": agrupar(lista_oferta, "ciclo"),
        "instituciones": instituciones,
    }
