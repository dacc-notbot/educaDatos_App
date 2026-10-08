"""Estadísticas agregadas con las unidades y campos publicados por ICETEX."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
import re
from time import monotonic

from config import REQUEST_TIMEOUT
from services.directorio_colegios import literal_soql
from services.socrata_service import consultar_dataset
from utils.normalizacion import valor_a_numero, normalizar_texto


PLAZO_CONSULTA_ICETEX = 120.0
ERROR_PLAZO = "La consulta de ICETEX tardó demasiado. Vuelve a intentarlo más tarde."
# Las descargas iniciadas no se pueden interrumpir desde un Future. Un pool
# compartido evita acumular hilos si una consulta falla mientras otras siguen.
_executor_fuentes = ThreadPoolExecutor(max_workers=4, thread_name_prefix="icetex-fuente")


def crear_plazo_icetex():
    return monotonic() + PLAZO_CONSULTA_ICETEX


def _tiempo_restante(plazo):
    restante = plazo - monotonic()
    if restante <= 0:
        raise RuntimeError(ERROR_PLAZO)
    return restante


def _consultar_fuente(dataset, params, plazo):
    # Comprueba también al iniciar una tarea que estuvo esperando en la cola.
    restante = _tiempo_restante(plazo)
    filas = consultar_dataset(
        dataset, limit=5000, params_extra=params,
        timeout=min(REQUEST_TIMEOUT, restante),
    )
    _tiempo_restante(plazo)
    return filas


def _consultar_serie(dataset, params, plazo):
    futuro = _executor_fuentes.submit(_consultar_fuente, dataset, params, plazo)
    try:
        # Este plazo incluye esperas por la caché y por un hilo disponible.
        return futuro.result(timeout=_tiempo_restante(plazo))
    except TimeoutError as error:
        raise RuntimeError(ERROR_PLAZO) from error
    finally:
        futuro.cancel()


def _reunir_distribuciones(agrupar, dimensiones, plazo):
    futuros = {}
    resultados = [None] * len(dimensiones)
    try:
        _tiempo_restante(plazo)
        for indice, dimension in enumerate(dimensiones):
            futuros[_executor_fuentes.submit(agrupar, dimension)] = indice
        # Recibe el primer error aunque una dimensión anterior esté bloqueada.
        for futuro in as_completed(futuros, timeout=_tiempo_restante(plazo)):
            resultados[futuros[futuro]] = futuro.result()
        _tiempo_restante(plazo)
        return resultados
    except TimeoutError as error:
        raise RuntimeError(ERROR_PLAZO) from error
    finally:
        # No espera las tareas ya iniciadas ni publica resultados parciales.
        for futuro in futuros:
            futuro.cancel()

DIMENSIONES = [
    ("departamento_de_origen", "Departamento de origen", "Lugar de origen reportado; no es la ubicación de una universidad."),
    ("nivel_de_formacion", "Nivel de formación", "Nivel educativo reportado por la fuente."),
    ("modalidad_de_linea", "Línea de financiación", "Línea a la que pertenece el crédito."),
    ("modalidad_del_credito", "Destino del crédito", "Concepto financiado, por ejemplo matrícula o sostenimiento."),
    ("sector_ies", "Sector de la institución", "Sector reportado; la fuente no identifica las instituciones por nombre."),
    ("sexo_al_nacer", "Sexo reportado", "Campo «sexo al nacer» publicado por ICETEX."),
    ("estrato_socio_economico", "Estrato socioeconómico", "Estrato reportado; no equivale a una medición de ingresos."),
    ("categoria_del_municipio_de", "Tipo de territorio de origen", "Clasificación del territorio; no identifica un municipio específico."),
    ("rango_del_valor_total", "Rango de desembolso", "La fuente publica códigos de rango, no montos exactos en pesos. No se convierten estos códigos en dinero."),
]


def extraer_filtros_icetex(pregunta):
    """Filtros explícitos habituales; nunca infiere características personales."""
    p = normalizar_texto(pregunta)
    filtros = {}
    opciones = [
        (r"\bpregrado\b", "modalidad_de_linea", "PREGRADO"),
        (r"\b(?:posgrado|postgrado)\b", "modalidad_de_linea", "POSGRADO PAÍS"),
        (r"\b(?:credito exterior|en el exterior)\b", "modalidad_de_linea", "CRÉDITO EXTERIOR"),
        (r"\b(?:mujeres|femenino)\b", "sexo_al_nacer", "Femenino"),
        (r"\b(?:hombres|masculino)\b", "sexo_al_nacer", "Masculino"),
        (r"\b(?:universidades|instituciones|sector) (?:de |del sector )?(?:privadas|privados|privado)\b", "sector_ies", "PRIVADO"),
        (r"\b(?:universidades|instituciones|sector) (?:de |del sector )?(?:publicas|publicos|oficial|oficiales)\b", "sector_ies", "OFICIAL"),
        (r"\bmatricula\b", "modalidad_del_credito", "MATRICULA"),
        (r"\bsostenimiento\b", "modalidad_del_credito", "SOSTENIMIENTO"),
        (r"\bmaestria\b", "nivel_de_formacion", "Maestría"),
        (r"\bdoctorado\b", "nivel_de_formacion", "Doctorado"),
    ]
    candidatos = {}
    for patron, campo, valor in opciones:
        if re.search(patron, p):
            candidatos.setdefault(campo, set()).add(valor)
    # Una petición de comparar ambos valores no se transforma en uno solo.
    filtros.update({campo: next(iter(valores)) for campo, valores in candidatos.items() if len(valores) == 1})
    estrato = re.search(r"\bestrato\s+([0-6])\b", p)
    if estrato and len(re.findall(r"\bestrato\s+[0-6]\b", p)) == 1:
        filtros["estrato_socio_economico"] = estrato.group(1)
    return filtros


def dimension_solicitada(pregunta, tipo="otorgados"):
    p = normalizar_texto(pregunta)
    opciones = [
        (r"\b(?:evolucion|historico|historia|tendencia|por ano|por anio)\b", "serie_anual"),
        (r"\b(?:rango|rangos|pesos|monto|montos|dinero)\b", "rango_del_valor_total"),
        (r"\b(?:sexo|mujeres|hombres|femenino|masculino)\b", "sexo_al_nacer"),
        (r"\bestratos?\b", "estrato_socio_economico"),
        (r"\b(?:sector|universidades|instituciones)\b", "sector_ies"),
        (r"\b(?:matricula|sostenimiento|destino)\b", "modalidad_del_credito"),
        (r"\b(?:linea|lineas|pregrado|posgrado|postgrado|exterior)\b", "modalidad_de_linea"),
        (r"\b(?:rural|territorio|territorios)\b", "categoria_del_municipio_de"),
        (r"\bdepartamentos\b", "departamento_de_origen"),
        (r"\b(?:periodo|periodos|semestre|semestres)\b", "periodo_renovacion" if tipo == "renovados" else "periodo_otorgamiento"),
    ]
    return next((campo for patron, campo in opciones if re.search(patron, p)), "nivel_de_formacion")


def entero(valor):
    numero = valor_a_numero(valor)
    if numero is None or numero < 0 or numero != int(numero):
        raise RuntimeError("ICETEX no devolvió una cantidad válida para calcular las estadísticas.")
    return int(numero)


def consultar_estadisticas_icetex(departamento=None, municipio=None, tipo="otorgados", anio=None, filtros=None, *, _plazo=None):
    plazo = _plazo if _plazo is not None else crear_plazo_icetex()
    if tipo not in ("otorgados", "renovados"):
        raise ValueError("Elige créditos otorgados o renovados.")
    if anio is not None and (not isinstance(anio, int) or not 1900 <= anio <= 2100):
        raise ValueError("Indica un año válido.")
    renovados = tipo == "renovados"
    filtros = filtros or {}
    campos_permitidos = {d[0] for d in DIMENSIONES} - {"departamento_de_origen"}
    if any(c not in campos_permitidos or not isinstance(v, str) or not v.strip() or len(v) > 120 for c, v in filtros.items()):
        raise ValueError("El filtro no corresponde a un campo de ICETEX disponible.")
    dataset = "icetex_renovados" if renovados else "icetex_otorgados"
    medida = "numero_de_renovaciones" if renovados else "numero_de_nuevos_beneficiarios"
    unidad = "Renovaciones de crédito" if renovados else "Nuevos beneficiarios de crédito"
    explicacion = (
        "Cuenta renovaciones reportadas. Una persona puede renovar en varios periodos; no es un conteo de personas únicas."
        if renovados else
        "Suma los nuevos beneficiarios reportados por ICETEX. No identifica personas ni permite comprobar si aparecen en varios periodos."
    )
    territorio = departamento or "Colombia"
    datos = {"tipo_credito": tipo, "filtros_aplicados": filtros, "anio_usado": None, "total_creditos_o_beneficiarios_aproximado": None,
             "total_registros_vigencia": None, "muestra_icetex": [], "visualizacion_icetex": {
                 "unidad": unidad, "explicacion": explicacion, "territorio": territorio, "anio": None,
                 "total": None, "serie_anual": [], "distribuciones": [], "cobertura_disponible": False}}
    fuente = {"nombre": "Créditos renovados por ICETEX" if renovados else "Créditos otorgados por ICETEX",
              "url": "https://www.datos.gov.co/resource/" + ("nvcf-b8a3" if renovados else "26bn-e42j") + ".json"}
    resultado = {"tipo_consulta": "icetex_" + tipo,
                 "territorio_consultado": {"departamento": departamento, "municipio": municipio, "tipo": tipo},
                 "datos": datos, "hallazgos_principales": [], "fuentes_usadas": [fuente],
                 "limitaciones": [explicacion, "Estas fuentes no detallan ciudades ni nombres de universidades. El territorio corresponde al departamento de origen.",
                                  "Los datos describen financiación reportada; no son una oferta de créditos ni establecen requisitos para solicitarlos.", "El último año publicado puede estar sujeto a actualización y no garantiza que el reporte del año esté completo.", "Cada vista agrupa un campo de la fuente. Las vistas describen el mismo total y no se suman entre sí."],
                 "sugerencias_de_siguiente_pregunta": [f"ICETEX otorgados en {territorio}", f"ICETEX renovados en {territorio}", f"Evolución de ICETEX en {territorio}"]}
    if municipio:
        resultado["respuesta_corta"] = (
            f"Esta fuente de ICETEX no permite consultar {municipio} por ciudad. "
            + (f"Puedes consultar el departamento de {departamento}." if departamento else "Puedes consultar por departamento o para toda Colombia.")
        )
        return resultado

    condiciones = [f"upper(departamento_de_origen) = {literal_soql(departamento)}"] if departamento else []
    for campo, valor in filtros.items():
        if campo == "estrato_socio_economico":
            if not valor.isdigit() or not 0 <= int(valor) <= 6:
                raise ValueError("Indica un estrato del 0 al 6.")
            condiciones.append(f"{campo} = {int(valor)}")
        else:
            condiciones.append(f"upper({campo}) = {literal_soql(valor)}")
    filtro = " AND ".join(condiciones) or None
    params = {"$select": f"vigencia, sum({medida}) as cantidad, count(*) as registros, count({medida}) as informados",
              "$group": "vigencia", "$order": "vigencia ASC"}
    if filtro:
        params["$where"] = filtro
    serie = _consultar_serie(dataset, params, plazo)
    if len(serie) >= 5000:
        raise RuntimeError("La serie de ICETEX supera la capacidad de consulta; no se presenta un total parcial.")
    temporal = []
    registros_anuales = {}
    for fila in serie:
        if fila.get("vigencia") is None:
            resultado["limitaciones"].append("La fuente contiene registros sin año, excluidos de la comparación anual.")
            continue
        year = entero(fila["vigencia"])
        if not 1900 <= year <= 2100:
            raise RuntimeError("La fuente de ICETEX informa un año inválido.")
        if entero(fila["registros"]) != entero(fila["informados"]):
            raise RuntimeError("Hay cantidades sin informar en la fuente de ICETEX; no se puede confirmar el total.")
        temporal.append({"anio": year, "cantidad": entero(fila["cantidad"])})
        registros_anuales[year] = entero(fila["registros"])
    _tiempo_restante(plazo)
    actual = anio if anio is not None else max(registros_anuales, default=None)
    resumen = next((fila for fila in temporal if fila["anio"] == actual), None)
    visual = datos["visualizacion_icetex"]
    visual.update({"anio": actual, "serie_anual": temporal, "cobertura_disponible": True})
    datos["anio_usado"] = actual
    if resumen is None:
        resultado["respuesta_corta"] = f"No hay datos de ICETEX {tipo} para {territorio}" + (f" en {actual}." if actual else ".")
        return resultado
    total = resumen["cantidad"]
    datos.update({"total_creditos_o_beneficiarios_aproximado": total, "total_registros_vigencia": registros_anuales[actual]})
    visual["total"] = total
    where = f"vigencia = {actual}" + (f" AND {filtro}" if filtro else "")
    periodo = "periodo_renovacion" if renovados else "periodo_otorgamiento"
    dimensiones = DIMENSIONES + [(periodo, "Periodo del año", "Periodo de otorgamiento o renovación dentro del año consultado.")]

    def agrupar(dimension):
        campo, titulo, nota = dimension
        filas = _consultar_fuente(dataset, {
            "$select": f"{campo} as categoria, sum({medida}) as cantidad",
            "$where": where, "$group": campo, "$order": "cantidad DESC"}, plazo)
        if len(filas) >= 5000:
            raise RuntimeError("Una distribución de ICETEX está incompleta; no se publica como total.")
        grupos = [{"categoria": str(f.get("categoria") or "Sin información"), "cantidad": entero(f.get("cantidad"))} for f in filas]
        if sum(f["cantidad"] for f in grupos) != total:
            raise RuntimeError("Los totales de ICETEX cambiaron o no coinciden entre consultas. Inténtalo más tarde.")
        return {"clave": campo, "titulo": titulo, "nota": nota, "filas": grupos,
                "permite_grafico": campo != "rango_del_valor_total"}

    visual["distribuciones"] = _reunir_distribuciones(agrupar, dimensiones, plazo)
    datos["consulta_completa"] = True
    cantidad = f"{total:,}".replace(",", ".")
    resultado["respuesta_corta"] = f"En {actual}, ICETEX reporta {cantidad} {unidad.lower()} para {territorio}. Puedes ver cómo se distribuyen y comparar los años disponibles."
    if filtros:
        resultado["respuesta_corta"] += " Filtros aplicados: " + ", ".join(f"{next(d[1] for d in DIMENSIONES if d[0] == c)}: {v}" for c, v in filtros.items()) + "."
    return resultado
