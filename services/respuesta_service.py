from typing import Any, Dict, List, Optional

try:
    from services.socrata_service import normalizar_texto
except Exception:
    def normalizar_texto(valor: Any) -> str:
        return str(valor or "").strip().lower()


# ============================================================
# Utilidades generales
# ============================================================

def limpiar_valor(valor: Any) -> str:
    """
    Convierte valores a texto limpio para mostrar al ciudadano.
    """
    if valor is None:
        return ""

    texto = str(valor).strip()

    if texto.lower() in ["none", "null", "nan", ""]:
        return ""

    return texto


def limitar_texto(texto: str, max_caracteres: int = 300) -> str:
    """
    Evita que valores demasiado largos saturen la respuesta.
    """
    texto = limpiar_valor(texto)

    if len(texto) <= max_caracteres:
        return texto

    return texto[:max_caracteres].rstrip() + "..."


def seleccionar_campos_relevantes(registro: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reduce un registro grande a campos útiles para lectura ciudadana.
    Como los datasets tienen columnas distintas, usa reglas flexibles.
    """
    campos_prioritarios = [
        # Identificación
        "nombre",
        "nom",
        "establecimiento",
        "institucion",
        "institución",
        "sede",
        "ies",
        "secretaria",
        "secretaría",
        "etc",

        # Territorio
        "departamento",
        "depto",
        "dpto",
        "municipio",
        "ciudad",
        "zona",
        "barrio",
        "vereda",

        # Educación básica y media
        "sector",
        "calendario",
        "caracter",
        "carácter",
        "grado",
        "nivel",
        "matricula",
        "matrícula",
        "cobertura",
        "desercion",
        "deserción",
        "aprobacion",
        "aprobación",
        "reprobacion",
        "reprobación",
        "repitencia",

        # Educación superior / ETDH
        "programa",
        "modalidad",
        "metodologia",
        "metodología",
        "area",
        "área",
        "nucleo",
        "núcleo",
        "estado",

        # Bachilleres / ICETEX
        "bachiller",
        "egresado",
        "graduado",
        "aprobados",
        "credito",
        "crédito",
        "beneficiario",
        "linea",
        "línea",

        # Temporalidad y datos
        "anio",
        "año",
        "ano",
        "a_o",
        "vigencia",
        "periodo",
        "valor",
        "total",
        "cantidad",

        # Ubicación/contacto
        "latitud",
        "longitud",
        "ubicacion",
        "ubicación",
        "direccion",
        "dirección",
        "telefono",
        "teléfono",
        "correo",
        "email",
    ]

    registro_filtrado = {}

    for campo, valor in registro.items():
        campo_norm = normalizar_texto(campo)

        if any(normalizar_texto(prioritario) in campo_norm for prioritario in campos_prioritarios):
            valor_limpio = limpiar_valor(valor)

            if valor_limpio:
                registro_filtrado[campo] = limitar_texto(valor_limpio)

    # Si no logró identificar campos prioritarios, devuelve los primeros campos útiles.
    if not registro_filtrado:
        for campo, valor in list(registro.items())[:10]:
            valor_limpio = limpiar_valor(valor)

            if valor_limpio:
                registro_filtrado[campo] = limitar_texto(valor_limpio)

    return registro_filtrado


def extraer_valores_frecuentes(
    resultados: List[Dict[str, Any]],
    patrones_columna: List[str],
    top_n: int = 5
) -> List[Dict[str, Any]]:
    """
    Busca columnas relevantes y devuelve valores frecuentes.
    Útil para explicar resultados genéricos sin conocer la estructura exacta.
    """
    if not resultados:
        return []

    columnas = set()

    for registro in resultados[:100]:
        columnas.update(registro.keys())

    columnas_candidatas = []

    for columna in columnas:
        columna_norm = normalizar_texto(columna)

        if any(normalizar_texto(p) in columna_norm for p in patrones_columna):
            columnas_candidatas.append(columna)

    if not columnas_candidatas:
        return []

    columna_usada = columnas_candidatas[0]
    conteo = {}

    for registro in resultados:
        valor = limpiar_valor(registro.get(columna_usada)) or "SIN DATO"
        conteo[valor] = conteo.get(valor, 0) + 1

    ordenados = sorted(conteo.items(), key=lambda x: x[1], reverse=True)[:top_n]

    return [
        {
            "columna": columna_usada,
            "valor": valor,
            "conteo": cantidad
        }
        for valor, cantidad in ordenados
    ]


# ============================================================
# Hallazgos ciudadanos
# ============================================================

def construir_hallazgos_principales(
    intencion: str,
    total_resultados: int,
    resultados: List[Dict[str, Any]]
) -> List[str]:
    """
    Construye hallazgos simples y claros a partir del tipo de consulta.
    """
    hallazgos = []

    if total_resultados == 0:
        return [
            "No se encontraron registros con los filtros utilizados.",
            "La ausencia de resultados no significa necesariamente que la información no exista; puede deberse al nombre usado, a la cobertura del dataset o a la forma como están registradas las columnas."
        ]

    if intencion in [
        "buscar_establecimientos_educativos",
        "consultar_establecimientos_educativos",
        "consultar_colegios",
        "colegios"
    ]:
        hallazgos.append(
            f"Se encontraron {total_resultados} registros relacionados con establecimientos educativos."
        )
        hallazgos.append(
            "Los resultados pueden incluir sedes, instituciones oficiales y no oficiales, según la estructura del dataset."
        )

    elif intencion in [
        "buscar_programas_educacion_superior",
        "consultar_programas_superior",
        "programas_superior",
        "educacion_superior"
    ]:
        hallazgos.append(
            f"Se encontraron {total_resultados} registros asociados con programas de educación superior."
        )
        hallazgos.append(
            "La consulta puede incluir programas por institución, metodología, municipio, departamento, estado o área de conocimiento."
        )

    elif intencion in [
        "buscar_instituciones_etdh",
        "instituciones_etdh"
    ]:
        hallazgos.append(
            f"Se encontraron {total_resultados} registros relacionados con instituciones de educación para el trabajo y desarrollo humano."
        )
        hallazgos.append(
            "Estos resultados sirven para explorar opciones de formación laboral o técnica en el territorio consultado."
        )

    elif intencion in [
        "buscar_programas_etdh",
        "programas_etdh"
    ]:
        hallazgos.append(
            f"Se encontraron {total_resultados} registros relacionados con programas de formación para el trabajo."
        )
        hallazgos.append(
            "La información permite revisar programas técnicos laborales o de formación por competencias."
        )

    elif intencion in [
        "consultar_bachilleres",
        "bachilleres"
    ]:
        hallazgos.append(
            f"Se encontraron {total_resultados} registros relacionados con bachilleres, egresados o aprobados de educación media."
        )
        hallazgos.append(
            "Estos datos pueden ayudar a analizar el tránsito entre educación media, educación superior y formación para el trabajo."
        )

    elif intencion in [
        "consultar_primera_infancia",
        "primera_infancia"
    ]:
        hallazgos.append(
            f"Se encontraron {total_resultados} registros relacionados con primera infancia o educación inicial."
        )
        hallazgos.append(
            "Estos datos pueden orientar preguntas sobre atención, cobertura o condiciones educativas en los primeros años."
        )

    elif intencion in [
        "consultar_creditos_icetex_otorgados",
        "consultar_creditos_icetex_renovados",
        "icetex_otorgados",
        "icetex_renovados",
        "icetex"
    ]:
        hallazgos.append(
            f"Se encontraron {total_resultados} registros relacionados con financiación educativa ICETEX."
        )
        hallazgos.append(
            "La información puede ayudar a explorar acceso, continuidad o distribución territorial de créditos educativos."
        )

    elif intencion in [
        "analizar_transito_educativo",
        "cruce_transito_educativo",
        "transito_educativo"
    ]:
        hallazgos.append(
            f"Se encontraron {total_resultados} registros útiles para explorar tránsito educativo."
        )
        hallazgos.append(
            "La lectura debe entenderse como descriptiva y exploratoria, no como una prueba de causalidad."
        )

    elif intencion in [
        "consultar_cluster_municipio",
        "consultar_grupo_estadistico",
        "buscar_municipios_similares",
        "generar_recomendaciones_municipio"
    ]:
        hallazgos.append(
            f"Se encontraron {total_resultados} registros asociados con agrupación estadística educativa."
        )
        hallazgos.append(
            "La agrupación estadística compara municipios con comportamiento educativo similar; no es un ranking de calidad."
        )

    elif intencion in [
        "diagnostico_territorial",
        "diagnostico_educativo"
    ]:
        hallazgos.append(
            f"Se encontraron {total_resultados} registros para apoyar el diagnóstico educativo territorial."
        )
        hallazgos.append(
            "El diagnóstico integra datos abiertos y debe interpretarse como una lectura exploratoria."
        )

    elif intencion == "buscar_zonas_wifi":
        hallazgos.append(
            f"Se encontraron {total_resultados} registros relacionados con zonas wifi o conectividad."
        )
        hallazgos.append(
            "Estos datos pueden cruzarse con información educativa para analizar condiciones de acceso digital."
        )

    elif intencion == "buscar_barrios_veredas":
        hallazgos.append(
            f"Se encontraron {total_resultados} registros territoriales relacionados con barrios, veredas o sectores."
        )
        hallazgos.append(
            "Esta información puede servir como apoyo para ubicar consultas educativas locales."
        )

    else:
        hallazgos.append(
            f"Se encontraron {total_resultados} registros en el dataset educativo seleccionado."
        )
        hallazgos.append(
            "La información debe interpretarse según las columnas disponibles, la vigencia y la cobertura del dataset."
        )

    # Complementos automáticos
    distribucion_sector = extraer_valores_frecuentes(
        resultados,
        ["sector", "naturaleza", "oficial", "privado"],
        top_n=3
    )

    if distribucion_sector:
        resumen = ", ".join(
            f"{item['valor']}: {item['conteo']}"
            for item in distribucion_sector
        )
        hallazgos.append(f"Valores frecuentes en la columna '{distribucion_sector[0]['columna']}': {resumen}.")

    distribucion_anio = extraer_valores_frecuentes(
        resultados,
        ["anio", "año", "ano", "vigencia", "periodo"],
        top_n=3
    )

    if distribucion_anio:
        resumen = ", ".join(
            f"{item['valor']}: {item['conteo']}"
            for item in distribucion_anio
        )
        hallazgos.append(f"Vigencias o periodos frecuentes detectados: {resumen}.")

    return hallazgos


def construir_respuesta_corta(
    pregunta: str,
    intencion: str,
    dataset_nombre: str,
    total_resultados: int
) -> str:
    """
    Genera una respuesta breve, clara y ciudadana.
    """
    if total_resultados == 0:
        return (
            "No encontré registros con esos filtros en el dataset consultado. "
            "Puedes intentar con otro nombre del municipio, departamento, institución, programa o entidad."
        )

    if intencion in [
        "consultar_cluster_municipio",
        "consultar_grupo_estadistico",
        "buscar_municipios_similares",
        "generar_recomendaciones_municipio"
    ]:
        return (
            f"Consulté el dataset '{dataset_nombre}' y encontré {total_resultados} registros relacionados. "
            "La lectura permite explorar grupos de municipios con comportamiento educativo similar."
        )

    if intencion in [
        "analizar_transito_educativo",
        "cruce_transito_educativo",
        "transito_educativo"
    ]:
        return (
            f"Consulté el dataset '{dataset_nombre}' y encontré {total_resultados} registros relacionados. "
            "La información ayuda a explorar el tránsito entre bachilleres, educación superior y financiación educativa."
        )

    return (
        f"Para tu pregunta, consulté el dataset '{dataset_nombre}' y encontré "
        f"{total_resultados} registros relacionados. A continuación se muestran los principales "
        "resultados disponibles para orientar la consulta ciudadana."
    )


def construir_limitaciones(total_resultados: int, intencion: Optional[str] = None) -> List[str]:
    """
    Limitaciones generales para evitar afirmaciones absolutas.
    """
    limitaciones = [
        "La respuesta depende de la actualización, cobertura y estructura del dataset publicado en datos.gov.co.",
        "Los resultados corresponden a registros disponibles; no reemplazan la verificación directa con la entidad responsable.",
        "Algunos nombres pueden aparecer con variaciones de escritura, abreviaturas o campos incompletos."
    ]

    if intencion in [
        "consultar_cluster_municipio",
        "consultar_grupo_estadistico",
        "buscar_municipios_similares",
        "generar_recomendaciones_municipio"
    ]:
        limitaciones.append(
            "La agrupación estadística identifica similitudes entre municipios, no causalidad ni calidad educativa definitiva."
        )

    if intencion in [
        "analizar_transito_educativo",
        "cruce_transito_educativo",
        "transito_educativo",
        "diagnostico_territorial",
        "diagnostico_educativo"
    ]:
        limitaciones.append(
            "La lectura es descriptiva y exploratoria; no prueba relaciones causales entre las variables."
        )

    if total_resultados == 0:
        limitaciones.append(
            "Puede ser necesario ampliar la búsqueda, revisar columnas o usar términos alternativos."
        )

    return limitaciones


def construir_sugerencias(intencion: str) -> List[str]:
    """
    Sugiere próximas preguntas útiles para el ciudadano.
    """
    if intencion in [
        "buscar_establecimientos_educativos",
        "consultar_establecimientos_educativos",
        "consultar_colegios",
        "colegios"
    ]:
        return [
            "¿Cuáles de estos establecimientos son oficiales o privados?",
            "¿Qué sedes aparecen en el municipio consultado?",
            "¿Puedo cruzar estos colegios con indicadores de cobertura o permanencia?"
        ]

    if intencion in [
        "buscar_programas_educacion_superior",
        "consultar_programas_superior",
        "programas_superior",
        "educacion_superior"
    ]:
        return [
            "¿Qué instituciones ofrecen esos programas?",
            "¿Qué programas hay por modalidad o área de conocimiento?",
            "¿Cómo se relaciona esta oferta con los bachilleres del territorio?"
        ]

    if intencion in ["buscar_instituciones_etdh", "buscar_programas_etdh", "instituciones_etdh", "programas_etdh"]:
        return [
            "¿Qué programas técnicos laborales hay en este municipio?",
            "¿Qué instituciones ETDH aparecen registradas?",
            "¿Cómo se relaciona esta oferta con empleo o tránsito desde la educación media?"
        ]

    if intencion == "buscar_zonas_wifi":
        return [
            "¿Qué zonas wifi quedan cerca de instituciones educativas?",
            "¿Cómo se puede cruzar conectividad con cobertura educativa?",
            "¿Qué municipios tienen menos registros de conectividad?"
        ]

    if intencion in [
        "consultar_bachilleres",
        "consultar_creditos_icetex_otorgados",
        "consultar_creditos_icetex_renovados",
        "bachilleres",
        "icetex"
    ]:
        return [
            "¿Cómo se relacionan bachilleres, oferta educativa superior y créditos ICETEX?",
            "¿Qué tendencia se observa por año o territorio?",
            "¿Qué brechas pueden identificarse en el acceso a educación superior?"
        ]

    if intencion in [
        "consultar_cluster_municipio",
        "consultar_grupo_estadistico",
        "buscar_municipios_similares",
        "generar_recomendaciones_municipio"
    ]:
        return [
            "¿Qué municipios tienen comportamiento educativo similar?",
            "¿Qué recomendaciones educativas se pueden generar para este municipio?",
            "¿Cómo se relaciona este grupo estadístico con bachilleres, educación superior e ICETEX?"
        ]

    if intencion in [
        "diagnostico_territorial",
        "diagnostico_educativo",
        "analizar_transito_educativo",
        "cruce_transito_educativo",
        "transito_educativo"
    ]:
        return [
            "¿Qué recomendaciones educativas surgen para este territorio?",
            "¿Qué municipios tienen condiciones educativas similares?",
            "¿Cómo se relacionan bachilleres, educación superior e ICETEX?"
        ]

    return [
        "¿Quieres filtrar por municipio o departamento?",
        "¿Quieres ver las columnas disponibles del dataset?",
        "¿Quieres cruzar esta información con otro dataset educativo?"
    ]


# ============================================================
# Constructor principal
# ============================================================

def construir_respuesta_ciudadana(
    pregunta: str,
    intencion: str,
    dataset_key: str,
    dataset: Dict[str, Any],
    total_resultados: int,
    resultados: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Construye una salida ciudadana, trazable y útil para el GPT.

    Esta función se usa principalmente para consultas genéricas. Los servicios
    especializados pueden devolver su propia respuesta ciudadana.
    """
    resultados_muestra = [
        seleccionar_campos_relevantes(registro)
        for registro in resultados[:10]
    ]

    fuente = {
        "dataset_key": dataset_key,
        "nombre": dataset.get("nombre"),
        "url": dataset.get("url"),
        "descripcion": dataset.get("descripcion"),
        "uso_principal": dataset.get("uso_principal"),
    }

    hallazgos = construir_hallazgos_principales(
        intencion=intencion,
        total_resultados=total_resultados,
        resultados=resultados
    )

    return {
        "respuesta_corta": construir_respuesta_corta(
            pregunta=pregunta,
            intencion=intencion,
            dataset_nombre=dataset.get("nombre", dataset_key),
            total_resultados=total_resultados
        ),
        "hallazgos_principales": hallazgos,
        "datos": {
            "intencion": intencion,
            "dataset_key": dataset_key,
            "total_resultados": total_resultados,
            "total_muestra": len(resultados_muestra),
            "resultados_muestra": resultados_muestra
        },
        # Se dejan ambos nombres para compatibilidad con main.py y servicios anteriores.
        "fuente_usada": fuente,
        "fuentes_usadas": [fuente],
        "resultados_muestra": resultados_muestra,
        "limitaciones": construir_limitaciones(
            total_resultados=total_resultados,
            intencion=intencion
        ),
        "sugerencias_de_siguiente_pregunta": construir_sugerencias(intencion)
    }