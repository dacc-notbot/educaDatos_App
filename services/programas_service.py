from typing import Any, Dict, List, Optional, Set
from collections import Counter
from services.busqueda_programas import coincide_nombre

from services.socrata_service import (
    consultar_dataset,
    normalizar_texto,
    seleccionar_columna_por_patrones,
)

from config import (
    MAX_LIMIT,
    DEFAULT_ANALYTIC_LIMIT,
    MIN_LIMIT_MUNICIPAL,
    MIN_LIMIT_DEPARTAMENTAL,
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


def resolver_limit_programas(
    departamento: Optional[str],
    municipio: Optional[str],
    texto: Optional[str],
    limit: Optional[int],
) -> int:
    """
    Define límites adecuados para consultas nacionales, departamentales o municipales.

    - Departamento completo: mínimo alto porque el volumen puede ser amplio.
    - Municipio o texto específico: mínimo alto para evitar muestras parciales.
    - Nunca supera MAX_LIMIT.
    """
    try:
        limit_solicitado = int(limit) if limit is not None else DEFAULT_ANALYTIC_LIMIT
    except (TypeError, ValueError):
        limit_solicitado = DEFAULT_ANALYTIC_LIMIT

    if departamento and not municipio and not texto:
        limit_final = max(limit_solicitado, MIN_LIMIT_DEPARTAMENTAL)
    elif municipio or texto:
        limit_final = max(limit_solicitado, MIN_LIMIT_MUNICIPAL)
    else:
        limit_final = max(limit_solicitado, DEFAULT_ANALYTIC_LIMIT)

    return min(limit_final, MAX_LIMIT)


def texto_completo_registro(registro: Dict[str, Any]) -> str:
    return normalizar_texto(" ".join(str(valor) for valor in registro.values()))


def obtener_municipios_departamento(departamento: Optional[str]) -> Set[str]:
    """
    Obtiene municipios de un departamento desde el catálogo territorial.
    Sirve cuando el dataset de programas no trae columna de departamento,
    pero sí trae municipio de la institución.
    """
    if not departamento:
        return set()

    try:
        from services.territorio_service import construir_catalogo_territorial
    except Exception:
        return set()

    departamento_norm = normalizar_texto(departamento)

    try:
        catalogo = construir_catalogo_territorial()
    except Exception:
        return set()

    municipios = set()

    for par in catalogo.get("pares", []):
        dep = normalizar_texto(par.get("departamento"))
        mun = normalizar_texto(par.get("municipio"))

        if dep == departamento_norm and mun:
            municipios.add(mun)

    return municipios


def registro_coincide_territorio(
    registro: Dict[str, Any],
    departamento: Optional[str],
    municipio: Optional[str],
    col_departamento: Optional[str],
    col_municipio: Optional[str],
    municipios_departamento: Optional[Set[str]] = None,
) -> bool:
    """
    Filtra registros por territorio.

    Casos:
    - Si hay municipio, se compara con columna de municipio si existe.
    - Si hay departamento y existe columna de departamento, se compara directamente.
    - Si no hay columna de departamento, pero hay columna de municipio,
      se valida si el municipio pertenece al departamento consultado.
    - Si no hay columnas claras, se usa texto completo como respaldo.
    """
    texto_completo = None

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

    if departamento:
        departamento_norm = normalizar_texto(departamento)

        if col_departamento:
            valor_departamento = normalizar_texto(registro.get(col_departamento))
            if valor_departamento != departamento_norm:
                return False

        elif col_municipio and municipios_departamento:
            valor_municipio = normalizar_texto(registro.get(col_municipio))
            if valor_municipio not in municipios_departamento:
                return False

        else:
            if texto_completo is None:
                texto_completo = texto_completo_registro(registro)
            if departamento_norm not in texto_completo:
                return False

    return True


def registro_coincide_texto(registro: Dict[str, Any], texto: Optional[str]) -> bool:
    if not texto:
        return True

    texto_norm = normalizar_texto(texto)

    if not texto_norm:
        return True

    return texto_norm in texto_completo_registro(registro)


def contar_unicos(
    registros: List[Dict[str, Any]], columna: Optional[str]
) -> Optional[int]:
    if not registros or not columna:
        return None

    valores = set()

    for registro in registros:
        valor = limpiar_valor(registro.get(columna))

        if valor:
            valores.add(normalizar_texto(valor))

    return len(valores)


def distribucion_por_columna(
    registros: List[Dict[str, Any]], columna: Optional[str], top_n: int = 10
) -> List[Dict[str, Any]]:
    if not registros or not columna:
        return []

    contador = Counter()

    for registro in registros:
        valor = limpiar_valor(registro.get(columna)) or "SIN DATO"
        contador[valor] += 1

    return [
        {"valor": valor, "conteo": conteo}
        for valor, conteo in contador.most_common(top_n)
    ]


def es_programa_activo(registro: Dict[str, Any], col_estado: Optional[str]) -> bool:
    if not col_estado:
        return False

    estado = normalizar_texto(registro.get(col_estado))

    return estado == "activo"


def construir_muestra_programas(
    registros: List[Dict[str, Any]],
    col_programa: Optional[str],
    col_institucion: Optional[str],
    col_estado: Optional[str],
    col_nivel: Optional[str],
    col_metodologia: Optional[str],
    col_area: Optional[str],
    col_municipio: Optional[str],
    col_departamento: Optional[str],
    col_titulo: Optional[str] = None,
    max_items: Optional[int] = 10,
) -> List[Dict[str, Any]]:
    """
    Construye una muestra legible para ciudadanía.

    Si existe estado del programa, prioriza programas activos en la muestra.
    """
    muestra = []
    vistos = set()

    registros_ordenados = sorted(
        registros, key=lambda r: 0 if es_programa_activo(r, col_estado) else 1
    )

    for registro in registros_ordenados:
        programa = (
            limpiar_valor(registro.get(col_programa or col_titulo))
            if (col_programa or col_titulo)
            else ""
        )
        institucion = (
            limpiar_valor(registro.get(col_institucion)) if col_institucion else ""
        )

        if not programa and not institucion:
            continue

        clave = tuple(
            normalizar_texto(registro.get(columna)) if columna else ""
            for columna in (
                col_programa or col_titulo,
                col_institucion,
                col_estado,
                col_nivel,
                col_municipio,
                col_metodologia,
            )
        )

        if clave in vistos:
            continue

        vistos.add(clave)

        item = {}

        if programa:
            item["programa" if col_programa else "titulo_obtenido"] = programa

        if institucion:
            item["institucion"] = institucion

        if col_estado:
            estado = limpiar_valor(registro.get(col_estado))
            if estado:
                item["estado"] = estado

        if col_nivel:
            nivel = limpiar_valor(registro.get(col_nivel))
            if nivel:
                item["nivel"] = nivel

        if col_metodologia:
            metodologia = limpiar_valor(registro.get(col_metodologia))
            if metodologia:
                item["metodologia_modalidad"] = metodologia

        if col_area:
            area = limpiar_valor(registro.get(col_area))
            if area:
                item["area_conocimiento"] = area

        if col_municipio:
            municipio = limpiar_valor(registro.get(col_municipio))
            if municipio:
                item["municipio"] = municipio

        if col_departamento:
            departamento = limpiar_valor(registro.get(col_departamento))
            if departamento:
                item["departamento"] = departamento

        muestra.append(item)

        if max_items is not None and len(muestra) >= max_items:
            break

    return muestra


def filtrar_registros_activos(
    registros: List[Dict[str, Any]], col_estado: Optional[str]
) -> List[Dict[str, Any]]:
    if not registros or not col_estado:
        return []

    return [
        registro for registro in registros if es_programa_activo(registro, col_estado)
    ]


# ============================================================
# Servicio principal
# ============================================================


def consultar_programas_superior_service(
    departamento: Optional[str] = None,
    municipio: Optional[str] = None,
    texto: Optional[str] = None,
    limit: int = DEFAULT_ANALYTIC_LIMIT,
    estado: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Consulta programas de educación superior de forma ciudadana:
    - filtra por departamento o municipio,
    - identifica programas únicos,
    - identifica instituciones,
    - resume nivel, metodología/modalidad, estado y área de conocimiento.

    Para consultas departamentales evita $q cuando no hay texto específico,
    porque $q puede traer una muestra parcial. En ese caso descarga más registros
    y filtra localmente.
    """
    if not departamento and not municipio and not texto:
        raise ValueError(
            "Debes indicar un departamento, municipio o texto de búsqueda para consultar programas de educación superior."
        )

    limit_final = resolver_limit_programas(
        departamento=departamento, municipio=municipio, texto=texto, limit=limit
    )

    # Los nombres se buscan en títulos e instituciones, sin depender de $q ni de áreas generales.
    q_inicial = None

    registros = consultar_dataset(
        dataset_key="programas_superior", limit=limit_final, q=q_inicial
    )

    fuente = {
        "dataset_key": "programas_superior",
        "nombre": "Programas de educación superior",
        "url": "https://www.datos.gov.co/resource/upr9-nkiz.json",
    }

    if not registros:
        territorio = municipio or departamento or texto or "el filtro consultado"

        return {
            "tipo_consulta": "programas_superior",
            "territorio_consultado": {
                "departamento": departamento,
                "municipio": municipio,
                "texto": texto,
            },
            "respuesta_corta": (
                f"No encontré registros de programas de educación superior para {territorio} "
                "con los filtros usados."
            ),
            "hallazgos_principales": [
                "No se encontraron programas en la consulta inicial.",
                "Puedes intentar con otro municipio, departamento, institución o nombre de programa.",
            ],
            "datos": {
                "limit_usado": limit_final,
                "q_inicial": q_inicial,
                "total_registros_descargados": 0,
                "total_registros": 0,
                "total_programas_unicos": 0,
                "total_programas_activos_unicos": None,
                "total_instituciones_unicas": 0,
                "distribucion_nivel": [],
                "distribucion_metodologia": [],
                "distribucion_area": [],
                "distribucion_estado": [],
                "instituciones_frecuentes": [],
                "programas_frecuentes": [],
                "columnas_detectadas": {},
                "muestra_programas": [],
            },
            "fuentes_usadas": [fuente],
            "limitaciones": [
                "La ausencia de resultados puede depender de la forma como aparece registrado el programa, municipio o institución."
            ],
            "sugerencias_de_siguiente_pregunta": [
                "¿Qué programas de educación superior hay en Medellín?",
                "¿Qué universidades ofrecen programas en Cali?",
                "¿Qué programas de ingeniería hay en Bogotá?",
            ],
        }

    col_departamento = seleccionar_columna_por_patrones(
        registros,
        [
            "nombredepartprograma",
            "nombredepartamentoprograma",
            "nombredepartinstitucion",
            "nombredepartamentoinstitucion",
            "departamentoinstitucion",
            "departamento_institucion",
            "departamento",
            "nombre_departamento",
            "nom_departamento",
        ],
        excluir=["codigo", "cod", "id"],
    )

    col_municipio = seleccionar_columna_por_patrones(
        registros,
        [
            "nombremunicipioprograma",
            "municipio_programa",
            "nombremunicipioinstitucion",
            "municipioinstitucion",
            "municipio_institucion",
            "municipio",
            "ciudad",
            "nombre_municipio",
            "nom_municipio",
        ],
        excluir=["codigo", "cod", "id"],
    )

    col_codigo_programa = seleccionar_columna_por_patrones(
        registros, ["codigoprograma", "codigo_programa", "codigo_snies_programa"]
    )
    col_programa = seleccionar_columna_por_patrones(
        registros,
        [
            "nombreprograma",
            "nombre_programa",
            "nombreprogramaacademico",
            "nombre_programa_academico",
            "nombre_del_programa",
            "nombre del programa",
            "programaacademico",
            "programa_academico",
            "programa",
        ],
        excluir=[
            "codigo",
            "cod",
            "id",
            "snies",
            "estado",
            "activo",
            "inactivo",
            "municipio",
            "departamento",
            "institucion",
            "institución",
            "nivel",
            "metodologia",
            "metodología",
            "modalidad",
            "area",
            "área",
        ],
    )

    col_institucion = seleccionar_columna_por_patrones(
        registros,
        [
            "nombreinstitucion",
            "nombre_institucion",
            "nombreinstitucioneducacionsuperior",
            "nombre_institucion_educacion_superior",
            "nombre_institucion_educación_superior",
            "nombreies",
            "nombre_ies",
            "institucioneducacionsuperior",
            "institucion_educacion_superior",
            "institución_educación_superior",
            "ies",
            "institucion",
            "institución",
        ],
        excluir=[
            "codigo",
            "cod",
            "id",
            "snies",
            "municipio",
            "ciudad",
            "departamento",
            "programa",
            "estado",
            "nivel",
            "metodologia",
            "metodología",
            "modalidad",
        ],
    )

    col_titulo = seleccionar_columna_por_patrones(
        registros, ["nombretituloobtenido", "titulo_obtenido"]
    )
    muestra_identificacion = [
        r for r in registros[:200] if r.get(col_programa) and r.get(col_departamento)
    ]
    identificacion_confiable = bool(col_programa) and (
        not muestra_identificacion
        or sum(
            normalizar_texto(r[col_programa]) == normalizar_texto(r[col_departamento])
            for r in muestra_identificacion
        )
        / len(muestra_identificacion)
        < 0.8
    )
    if not identificacion_confiable:
        # La fuente upr9-nkiz publica actualmente departamentos en nombreprograma
        # y códigos de departamento en codigoprograma. No son IDs de programas.
        col_programa = None
        col_codigo_programa = None

    col_estado = seleccionar_columna_por_patrones(
        registros,
        ["nombreestadoprograma", "estado_programa", "estado", "estadoprograma"],
        excluir=["codigo", "cod", "id"],
    )

    col_nivel = seleccionar_columna_por_patrones(
        registros,
        [
            "nombrenivelformacion",
            "nivel_formacion",
            "nivel_formación",
            "nivelacademico",
            "nivel_academico",
            "nivel_académico",
            "nivel académico",
            "nivel",
        ],
        excluir=["codigo", "cod", "id"],
    )

    col_metodologia = seleccionar_columna_por_patrones(
        registros,
        ["nombremetodologia", "metodologia", "metodología", "modalidad"],
        excluir=["codigo", "cod", "id"],
    )

    col_area = seleccionar_columna_por_patrones(
        registros,
        [
            "nombreareaconocimiento",
            "area_conocimiento",
            "área_conocimiento",
            "área de conocimiento",
            "area de conocimiento",
            "nombre_area",
            "nucleo_basico_conocimiento",
            "núcleo_basico_conocimiento",
            "núcleo",
            "nucleo",
            "area",
            "área",
        ],
        excluir=["codigo", "cod", "id"],
    )

    municipios_departamento = obtener_municipios_departamento(departamento)

    registros_filtrados = [
        registro
        for registro in registros
        if registro_coincide_territorio(
            registro=registro,
            departamento=departamento,
            municipio=municipio,
            col_departamento=col_departamento,
            col_municipio=col_municipio,
            municipios_departamento=municipios_departamento,
        )
    ]

    registros_filtrados = [
        registro
        for registro in registros_filtrados
        if not texto
        or coincide_nombre(
            texto,
            [
                registro.get(columna)
                for columna in (col_programa, col_titulo, col_institucion)
                if columna
            ],
        )
    ]
    if estado:
        registros_filtrados = [
            r
            for r in registros_filtrados
            if col_estado
            and normalizar_texto(r.get(col_estado)) == normalizar_texto(estado)
        ]

    total_registros = len(registros_filtrados)

    registros_activos = filtrar_registros_activos(
        registros=registros_filtrados, col_estado=col_estado
    )

    total_programas_unicos = (
        contar_unicos(registros_filtrados, col_codigo_programa or col_programa)
        or total_registros
    )

    total_programas_activos_unicos = (
        contar_unicos(registros_activos, col_codigo_programa or col_programa)
        if registros_activos
        else None
    )

    total_instituciones_unicas = (
        contar_unicos(registros_filtrados, col_institucion) or 0
    )
    total_titulos_distintos = contar_unicos(registros_filtrados, col_titulo)
    if not identificacion_confiable:
        total_programas_unicos = None
        total_programas_activos_unicos = None

    distribucion_nivel = distribucion_por_columna(registros_filtrados, col_nivel)

    distribucion_metodologia = distribucion_por_columna(
        registros_filtrados, col_metodologia
    )

    distribucion_area = distribucion_por_columna(registros_filtrados, col_area)

    distribucion_estado = distribucion_por_columna(registros_filtrados, col_estado)

    instituciones_frecuentes = distribucion_por_columna(
        registros_filtrados, col_institucion, top_n=10
    )

    programas_frecuentes = distribucion_por_columna(
        registros_filtrados, col_programa, top_n=10
    )

    muestra = construir_muestra_programas(
        registros=registros_filtrados,
        col_programa=col_programa,
        col_institucion=col_institucion,
        col_estado=col_estado,
        col_nivel=col_nivel,
        col_metodologia=col_metodologia,
        col_area=col_area,
        col_municipio=col_municipio,
        col_departamento=col_departamento,
        col_titulo=col_titulo,
        max_items=10,
    )

    lista_oferta = construir_muestra_programas(
        registros=registros_filtrados,
        col_programa=col_programa,
        col_institucion=col_institucion,
        col_estado=col_estado,
        col_nivel=col_nivel,
        col_metodologia=col_metodologia,
        col_area=col_area,
        col_municipio=col_municipio,
        col_departamento=col_departamento,
        col_titulo=col_titulo,
        max_items=None,
    )

    territorio = municipio or departamento or texto or "el filtro consultado"

    alcance = municipio or departamento or "Colombia"
    if texto:
        respuesta_corta = (
            f"Encontré {len(lista_oferta)} ofertas relacionadas con «{texto}» en {total_instituciones_unicas} instituciones de {alcance}. "
            "El listado muestra el título otorgado, la institución, el nivel académico y el estado reportado."
        )
    else:
        cantidad = (
            f"{total_titulos_distintos} títulos"
            if total_titulos_distintos is not None
            else f"{total_programas_unicos} programas"
            if total_programas_unicos is not None
            else "ofertas"
        )
        respuesta_corta = (
            f"En {alcance} se reportan {cantidad} de educación superior en {total_instituciones_unicas} instituciones. "
            "Puedes explorar el listado o buscar un programa por su nombre."
        )
    if not lista_oferta:
        respuesta_corta = f"No encontré ofertas relacionadas con «{texto or territorio}». Prueba con otra parte del nombre o cambia el territorio."
    advertencia_identificacion = (
        "La fuente presenta una inconsistencia en los nombres de programas. "
        "La búsqueda muestra títulos otorgados; no permite contar programas únicos."
    )
    hallazgos = []
    consulta_completa = len(registros) < limit_final

    return {
        "tipo_consulta": "programas_superior",
        "territorio_consultado": {
            "departamento": departamento,
            "municipio": municipio,
            "texto": texto,
        },
        "respuesta_corta": respuesta_corta,
        "hallazgos_principales": hallazgos,
        "datos": {
            "limit_usado": limit_final,
            "q_inicial": q_inicial,
            "total_registros_descargados": len(registros),
            "total_registros": total_registros,
            "total_programas_unicos": total_programas_unicos,
            "identificacion_programas_confiable": identificacion_confiable,
            "total_titulos_distintos": total_titulos_distintos,
            "total_programas_activos_unicos": total_programas_activos_unicos,
            "total_instituciones_unicas": total_instituciones_unicas,
            "distribucion_nivel": distribucion_nivel,
            "distribucion_metodologia": distribucion_metodologia,
            "distribucion_area": distribucion_area,
            "distribucion_estado": distribucion_estado,
            "instituciones_frecuentes": instituciones_frecuentes,
            "programas_frecuentes": programas_frecuentes,
            "columnas_detectadas": {
                "departamento": col_departamento,
                "municipio": col_municipio,
                "programa": col_programa,
                "codigo_programa": col_codigo_programa,
                "titulo_obtenido": col_titulo,
                "institucion": col_institucion,
                "estado": col_estado,
                "nivel": col_nivel,
                "metodologia": col_metodologia,
                "area": col_area,
            },
            "municipios_departamento_usados_para_filtrar": (
                sorted(municipios_departamento)
                if municipios_departamento and departamento and not col_departamento
                else []
            ),
            "muestra_programas": muestra,
            "lista_oferta": lista_oferta,
            "consulta_completa": consulta_completa,
            "territorio": {"departamento": departamento, "municipio": municipio},
            "texto_consultado": texto,
            "estado_consultado": estado,
        },
        "fuentes_usadas": [fuente],
        "limitaciones": [
            "El conteo corresponde a registros disponibles en datos.gov.co y puede variar según actualización del dataset.",
            "Un mismo programa puede aparecer varias veces por sede, modalidad, municipio, nivel o institución.",
            "Si el dataset no trae una columna clara de departamento, el filtro departamental se apoya en los municipios del catálogo territorial.",
            "La información debe verificarse con SNIES, la institución educativa o el MEN antes de tomar decisiones académicas.",
            "La presencia de programas activos o inactivos depende de la columna de estado detectada en el dataset.",
            *([advertencia_identificacion] if not identificacion_confiable else []),
            *(
                [
                    "La descarga alcanzó el límite de consulta; estos resultados pueden ser parciales."
                ]
                if not consulta_completa
                else []
            ),
        ],
        "sugerencias_de_siguiente_pregunta": [
            f"Ingeniería de sistemas en {alcance}",
            f"Psicología en {alcance}",
            f"Administración de empresas en {alcance}",
        ],
    }
